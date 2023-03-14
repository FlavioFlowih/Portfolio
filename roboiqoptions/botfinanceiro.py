# baixar livrarias necessarias
#!wget https://launchpad.net/~mario-mariomedina/+archive/ubuntu/talib/+files/libta-lib0_0.4.0-oneiric1_amd64.deb -qO libta.deb
#!wget https://launchpad.net/~mario-mariomedina/+archive/ubuntu/talib/+files/ta-lib0-dev_0.4.0-oneiric1_amd64.deb -qO ta.deb
#!dpkg -i libta.deb ta.deb
#!pip install ta-lib
#!pip install -U git+https://github.com/iqoptionapi/iqoptionapi.git
#!pip install -U git+https://github.com/Lu-Yi-Hsun/iqoptionapi.git
#!pip install pylint
#!pip install requests
#!pip install websocket-client==0.56
#!pip install talib-binary

# import dados
from iqoptionapi.stable_api import IQ_Option
from talib.abstract import *
import numpy as np
import logging
import time
import datetime as dt
from datetime import datetime
from dateutil import tz
import getpass
import json

import pandas as pd
import sys

# =========================
# Configurações do bot
# =========================
# Configurações pra pegar os kendons mais na frente
asset = "EURUSD"  #EURUSD-OTC
maxdict = 10
size = 300

timeframe = 60  # Para pegar os candles
expirations_mode = 1  # Expiração de 1 minuto
total = 0
total_conta = 0

ini_buy_amount = 1  # Valor inicial de compra
max_gales = 2         # Máximo de gales
buy_amount = ini_buy_amount        # Começar comprando pela variavel de compra inicial

last_loss = 0         # Valores de perda durante o periodo
last_gale = 0         # Contar quantos gales foram executados

stop_gain_day = 0       # Quando atingir este valor no dia (positivo), ele para o aplicativo 
stop_loss_day = 0       # Quando ele atingir este valor no dia (negativo), ele para o aplicativo
#stop_gain_week = 0       # Quando atingir este valor na semana (positivo), ele para o aplicativo 
stop_loss_week = 0       # Quando ele atingir este valor na semana (negativo), ele para o aplicativo

dinheiro_conta = 0     # Variavel atualizada com o valor da conta (posteriormente)

# Setamos tipo de conta que vamos a usar (real e praticas)
MODE = "PRACTICE" # /"REAL"
# Mensagem de erro caso der erro no login.
error_password="""{"code":"invalid_credentials","message":"You entered the wrong credentials. Please check that the login/password is correct."}"""

# Caso aconteça erro na api, evitamos que a tela fique poluida
logging.disable(level=(logging.DEBUG))


# Indicadores simples
periodo = 14
tempo_segundos = 60


# Como pegar os dados históricos dos candles em um intervalo pra atrás e fazemos um streaming dos próximos candles
ticks = []



# Variaveis para novas implementacoes:
# gerenciamento (foto enviada na ultima reuniao)
tipo_gale = 1   # 1 para % e 2 para valor fixo (numerico).
tipo_stop = 1   # 1 para % e 2 para valor fixo (numerico)
tipo_mode = 1   # 1 para PRACTICE e 2 para REAL.
tipo_entrada = 1 # 1 para % e 2 para valor fixo (numerico).
envio_sinal = 2  # 1 para sim e 2 para nao
delay_programado = 3

# programar sinal
expiration_sinal = expirations_mode
asset_sinal = ""
horario_sinal = ""
action_sinal = ""

# Funcao para formatar horario
def timestamp_converter(x):
  hora = datetime.strptime(datetime.utcfromtimestamp(x).strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
  hora = hora.replace(tzinfo=tz.gettz('GMT'))
  return str(hora.astimezone(tz.gettz('America/Sao Paulo')))[:-6]

# Função que vai parar o programa ao atingir os valores definidos
def stopsLoss(Iq):
  global total_conta, stop_loss_day, stop_loss_week, stop_gain_day
  #if total_conta <= stop_loss_week or total_conta <= stop_loss_day or total_conta >= stop_gain_day:
  dinheiro_conta = Iq.get_balance()
  print(f"Antes do if - Conta: ${dinheiro_conta} e stop: ${stop_loss_week}")
  if dinheiro_conta <= stop_loss_week or dinheiro_conta >= stop_gain_day:
    
    print(f"Conta: ${dinheiro_conta} e stop: ${stop_loss_week}")
    #!kill -9 -1
    sys.exit()

# Funcao que vai definir o mode (se a conta é de pratica ou teste)
def escolherMode():
  global MODE, tipo_mode, delay_programado
  print("=============================================")
  print("Digite o número para definir o tipo de conta que vai ser utilizada:")
  print("1) Pratica")
  print("2) Real")
  tipo_mode = int(input())
  print("=============================================")
  print("Digite o delay em segundos utilizado para as operações (max 60 e min 0): ")
  value_delay = int(input())
  if value_delay < 0:
    delay_programado = 0
  elif value_delay > 60:
    delay_programado = 60
  elif value_delay < 60 and value_delay > 0:
    delay_programado = value_delay

  if tipo_mode == 1:
    MODE = "PRACTICE"
  elif tipo_mode == 2:
    MODE = "REAL"

def escolherGerenciamentoConta(Iq):
  global tipo_gale, tipo_stop, dinheiro_conta, stop_loss_day, stop_gain_day, stop_loss_week, buy_amount, ini_buy_amount, total_conta
  # Atualiza o dinheiro com  o valor atual da conta e estabelece padrões
  dinheiro_conta = Iq.get_balance()
  total_conta = dinheiro_conta
  print("Dinheiro atual na conta: ", dinheiro_conta)
  escolherEntrada()
  # Definir tipo de stop e escolher valores:
  print("=============================================")
  # 1 para % e 2 para valor fixo (numerico)
  print("Digite o número para definir o tipo de stop que vai ser utilizado:")
  print("1) Porcentagem")
  print("2) Valor fixo")
  tipo_stop = int(input())
  if tipo_stop == 1:
    # tipo em porcentagem
    stop_loss = int(input("Limite de perda % (Recomendado 9):"))
    stop_loss_week = dinheiro_conta - (dinheiro_conta * (stop_loss / 100))
    stop_loss_day = stop_loss_week
    print("Valor de stop loss definido: ", stop_loss_week)
    stop_win = int(input("Limite de ganhos % (Recomendado 6):"))
    stop_gain_day = dinheiro_conta + (dinheiro_conta * (stop_win / 100))
    print("Valor de stop win definido: ", stop_gain_day)
  elif tipo_stop == 2:
    # tipo em valor fixo
    stop_loss = int(input("Limite de perda R$ (Exemplo: 100):"))
    stop_loss_week = dinheiro_conta - stop_loss
    stop_loss_day = stop_loss_week
    print("Valor de stop loss definido: ", stop_loss_week)
    stop_win = int(input("Limite de ganho definido R$ (Exemplo: 100):"))
    stop_gain_day = dinheiro_conta + stop_win
    print("Valor de stop win definido: ", stop_gain_day)
  print("=============================================")
  
def escolherEntrada():
  global tipo_entrada, buy_amount, ini_buy_amount
  # 1 para % e 2 para valor fixo (numerico).
  print("=============================================")
  print("Digite o o número para definir o tipo de entrada que vai ser utilizada:")
  print("1) Porcentagem")
  print("2) Valor fixo")
  tipo_entrada = int(input())
  if tipo_entrada == 1:
    value_entrada = int(input("Porcentagem (%) de entrada inicial (recomendado 3): "))
    buy_amount = dinheiro_conta * (int(value_entrada) / 100)
  elif tipo_entrada == 2:
    value_entrada = int(input("Valor (R$) de entrada inicial (Exemplo: 100): "))
    buy_amount = value_entrada

  ini_buy_amount = buy_amount
  print("Valor da entrada inicial: ", buy_amount)
  print("=============================================")


# Função baseada numa função do IQ Option que avalia se é hora de fazer entrada ou não
def is_time_trade(Iq):
  global delay_programado, envio_sinal, expiration_sinal, asset_sinal, horario_sinal, action_sinal, buy_amount
  minutos = float(((datetime.now()).strftime('%M.%S'))[1:]) # Pega os minutos e segundos em um intervalo de 10
  #print(minutos)

  define_delay = 60 - delay_programado
  if delay_programado == 0 or delay_programado == 60:
    define_delay = "00"
  enter = False
  
  #if minutos == 4.57 or minutos == 9.57:
  if envio_sinal == 2 and MODE == "PRACTICE":
    if minutos == float("1." + str(define_delay)) or minutos == float("3." + str(define_delay)) or minutos == float("5." + str(define_delay)) or minutos == float("7." + str(define_delay)) or minutos == float("9." + str(define_delay)):
    #if minutos == 1.57 or minutos == 3.57 or minutos == 5.57 or minutos == 7.57 or minutos == 9.57:
    #if minutos == 0.57 or minutos == 1.57 or minutos == 2.57 or minutos == 3.57 or minutos == 4.57 or minutos == 5.57 or minutos == 6.57 or minutos == 7.57 or minutos == 8.57 or minutos == 9.57:
      enter = True
  if envio_sinal == 1:
    #hora = int(((datetime.now()).strftime('%H'))) - 3 # Pega hora do Brasil
    hora = int(((datetime.now()).strftime('%H'))) # Pega hora do Brasil
    min = float(((datetime.now()).strftime('%M.%S'))) # Pega hora do Brasil
    #print(hora)
    #print(min)

    values = horario_sinal.split(":")
    hora_sinal = int(values[0])
    minutos_sinal = int(values[1])
    
    if delay_programado != 0:
      minutos_sinal = minutos_sinal - 1
      if minutos_sinal < 0:
        minutos_sinal = 59

    min_sinal_format = float(str(minutos_sinal) + "." + str(define_delay))
    #print(hora)
    #print(hora_sinal)
    #print(min_sinal_format)
    #print(min)

    if hora_sinal == hora and min_sinal_format == min:
      # Executa sinal
      print("Foi enviado o sinal!")
      order_check, order_id = Iq.buy(buy_amount, asset_sinal, action_sinal, expiration_sinal)
      # Função que pega os resultados vai validar e imprimir a resposta
      res = check_order(Iq, order_check, order_id)
      # Stop do robô caso ele atingir um dos limites
      stopsLoss(Iq)
      if res is not None:
        pay = payout(Iq)
        martingaleNew(Iq, res, action_sinal, True)

  return enter


# Atualiza valor total de dinheiro da conta e define os valores padrão de stop gain e stop loss com uma margem de porcentagem diária
def defMoneyValuesAccount(Iq):
  escolherGerenciamentoConta(Iq)

def programarSinal():
  global envio_sinal, expiration_sinal, asset_sinal, horario_sinal, action_sinal
  print("=============================================")
  print("Deseja programar um sinal? Digite o número.")
  print("1) Sim")
  print("2) Não")
  envio_sinal = int(input())
  if envio_sinal == 1:
    # executa input pra mostrar o envio de sinal
    print("Digite o sinal em formato 'EXPIRACAO MINUTOS;MERCADO;HORARIO;TIPO_TRADE': ")
    sinal = input("Exemplo: 5;EURUSD;12:00;CALL")
    values = sinal.split(";")
    expiration_sinal = values[0]
    asset_sinal = values[1]
    horario_sinal = values[2]
    action_sinal = values[3]
  print("=============================================")


# Função que valida a ordem para imprimir os resultados
def check_order(Iq, order_check, order_id):
  global total, last_loss, total_conta
  if order_check:
    # Se o parametro vir como true, quer dizer que vem com uma ordem
    result = Iq.check_binary_order(order_id)    # Recolhe os dados enviados pelo parametro
    if result['result']:
      # Se tiver resposta no result, faz o calculo para saber quanto ganhei/perdi em 2 casas decimais
      res = round(float(result['profit_amount']) - float(result['amount']), 2)
      total = round(total + res, 2)
      total_conta += round(total + res, 2)
      # Mostra resultado
      print(f'Resultado: {res} Total acumulado {total}')
      if res < 0:
        last_loss = round(float(res), 2)
      elif res > 0:
        last_loss = 0
      return res
    return None


# Função que vai fazer a contagem de martilgale, recebe o resultado da operação e o resultado do payout
def martingale(resultado, payout=0):
  #payout em decimal (ex: 0.87)
  global ini_buy_amount, buy_amount, last_loss, last_gale
  if last_gale < max_gales and resultado < 0:
    buy_amount = round(abs(last_loss) / float(payout), 2)   # conta pra somar o martingale (recupera a perca). Aqui só faz a conta pra ver quanto e perdeu e saber quanto deve usar na próxima entrada pra recuperar a perca
    last_gale += 1                                          # saber em qual gale esta atual
  elif resultado > 0 or last_gale >= max_gales:
    # reset valor de compra (ou seja, eu ganhei ou o gale atingiu o limite)
    buy_amount = ini_buy_amount
    last_gale = 0
    last_loss = 0

# Função que vai fazer martingale apos fazer opereacao
def martingaleNew(Iq, resultado, tipo_entrada, sinal = False):
  global ini_buy_amount, buy_amount, last_loss, last_gale, max_gales, asset_sinal, action_sinal, expiration_sinal
  if last_gale < max_gales and resultado < 0:
    # aumenta o gale e faz uma entrada com o contrario do asset
    last_gale += 1
    compra = buy_amount * 2
    if tipo_entrada == "call" and sinal == False:
      # fazer entrada tipo put
      order_check, order_id = Iq.buy(compra, asset, "put", expirations_mode)
      # Função que pega os resultados vai validar e imprimir a resposta
      res = check_order(Iq, order_check, order_id)
      # Stop do robô caso ele atingir um dos limites
      stopsLoss(Iq)
    if tipo_entrada == "put" and sinal == False:
      # fazer entrada tipo call
      order_check, order_id = Iq.buy(compra, asset, "call", expirations_mode)
      # Função que pega os resultados vai validar e imprimir a resposta
      res = check_order(Iq, order_check, order_id)
      # Stop do robô caso ele atingir um dos limites
      stopsLoss(Iq)
    if sinal == True:
      # fazer entrada tipo call
      order_check, order_id = Iq.buy(compra, asset_sinal, action_sinal, expiration_sinal)
      # Função que pega os resultados vai validar e imprimir a resposta
      res = check_order(Iq, order_check, order_id)
      # Stop do robô caso ele atingir um dos limites
      stopsLoss(Iq)
  elif resultado > 0 or last_gale >= max_gales:
    # reset valor de compra (ou seja, eu ganhei ou o gale atingiu o limite)
    buy_amount = ini_buy_amount
    last_gale = 0




# Função payout que recebe a instância da IQ Option e o tipo de moeda trabalhada
def payout(Iq):
  global asset
  # Retorna o binário de 1 a 5 min da moeda sendo utilizada
  return Iq.get_all_profit()[asset]['turbo']

# Atualiza valor do asset (mercado) segundo o que estiver aberto
def defAssetOpen(Iq):
  global asset
  ativos = Iq.get_all_open_time()
  # Checando se está aberto ou não
  if ativos["digital"]["EURUSD"]["open"] == True:
    asset = "EURUSD"
  elif ativos["digital"]["EURUSD-OTC"]["open"] == True:
    asset = "EURUSD-OTC"
  else:
    asset = ""
    status = False

# Função maioria que basicamente faz uma limpa na estrategia de mhi (basicamente é a mesma só que com menos coisas), pega todos os candles e faz um loop pra fazer a contagem
def maioria(opened, closed):
  # Valida a maioria
  # Args: 
  #   opened (pd.series): pandas series de open
  #   closed (pd.series): pandas series de close
  # Returns: [string|None]: put or call
  # init
  r = 0
  g = 0
  doji = 0
  # count
  for idx, val in enumerate(opened):
    if opened.iloc[idx] > closed.iloc[idx]:
      r += 1
    elif opened.iloc[idx] < closed.iloc[idx]:
      g += 1
    else:
      doji += 1
  
  signal = None
  if r > g and r > doji:
    signal = 'PUT'
  if g > r and g > doji:
    signal = 'CALL'
  #print(f'Maioria: R:{r} G:{g} D:{doji}')
  return signal



# Função de estrategia de trading com MHI
def mhi(opened, closed):
  # Valida se tem uma entrada mhi
  # Args:
  #   opened (pd.series): pandas series de open
  #   closed (pd.series): pandas series de close
  # Returns:
  #   [string|Nome]: put or call
  # Calcula mhi
  last_3_open = opened.tail(3)    # Como tem varios candles, quero somente os 3 ultimos que preciso
  last_3_close = closed.tail(3)   # Como tem varios candles, quero somente os 3 ultimos que preciso

  r = 0     # Variavel vermelha
  g = 0     # Variavel verde
  doji = 0  # Variavel dos doji
  for idx, val in enumerate(last_3_open):
    if last_3_open.iloc[idx] > last_3_close.iloc[idx]:
      # Se o open for maior que o close, quer dizer que open tá em cima e o close por baixo, ou seja, é vermelho
      r += 1
    elif last_3_open.iloc[idx] < last_3_close.iloc[idx]:
      # Se o open for menor que o close, quer dizer que o open tá em baixo e o close por cima, ou seja, é verde
      g += 1
    else: 
      # Se ele não entrar em nenhum, é um doje, ou seja, o valor não mudou
      doji += 1

  signal = None       # Variavel que especifica sem sinal
  # Verifica se não tem doji
  if doji == 0:
    if g >= 2:
      # Se a quantidade de vermelho é maior, então dá put
      signal = 'PUT'
    if r >= 2:
      # Se tiver mais verde, então compra
      signal = 'CALL'

  # Retorna signal que pode ser null, put ou call
  return signal

  
# Funcao que vai tentar pegar as medias moveis com variaveis
def obterMedMovel(Iq, periodo):
  #global tempo_segundos, periodo
  Iq.start_candles_stream(asset, tempo_segundos, int(periodo)+1)
  while True:
    velas = Iq.get_realtime_candles(asset, tempo_segundos)
    valores = {
      'open': np.array([]),
      'high': np.array([]),
      'low': np.array([]),
      'close': np.array([]),
      'volume': np.array([])
    }

    for x in velas:
      valores['open'] = np.append(valores['open'], velas[x]['open'])
      valores['high'] = np.append(valores['open'], velas[x]['max'])
      valores['low'] = np.append(valores['open'], velas[x]['min'])
      valores['close'] = np.append(valores['open'], velas[x]['close'])
      valores['volume'] = np.append(valores['open'], velas[x]['volume'])
    calculo_sma = SMA(valores, timeperiod=int(periodo))

# Funcao que vai tentar pegar as medias moveis com variaveis
def obterMedMovelExp(Iq, periodo):
  #global tempo_segundos, periodo
  Iq.start_candles_stream(asset, tempo_segundos, int(periodo)+1)
  while True:
    velas = Iq.get_realtime_candles(asset, tempo_segundos)
    valores = {
      'open': np.array([]),
      'high': np.array([]),
      'low': np.array([]),
      'close': np.array([]),
      'volume': np.array([])
    }

    for x in velas:
      valores['open'] = np.append(valores['open'], velas[x]['open'])
      valores['high'] = np.append(valores['open'], velas[x]['max'])
      valores['low'] = np.append(valores['open'], velas[x]['min'])
      valores['close'] = np.append(valores['open'], velas[x]['close'])
      valores['volume'] = np.append(valores['open'], velas[x]['volume'])
    calculo_sma = EMA(valores, timeperiod=int(periodo))

# Function para analisar medias moveis de 20 e 200
def tendenciaMedMovel20e200(Iq):
  velas = dadosVelas(Iq, 5, 20)
  velas200 = dadosVelas(Iq, 5, 200)
  valores = {
    'open': np.array([]),
    'high': np.array([]),
    'low': np.array([]),
    'close': np.array([]),
    'volume': np.array([])
  }

  valores200 = {
    'open': np.array([]),
    'high': np.array([]),
    'low': np.array([]),
    'close': np.array([]),
    'volume': np.array([])
  }

  for vela in velas:
    valores['open'] = np.append(valores['open'], vela['open'])
    valores['high'] = np.append(valores['open'], vela['max'])
    valores['low'] = np.append(valores['open'], vela['min'])
    valores['close'] = np.append(valores['open'], vela['close'])
    valores['volume'] = np.append(valores['open'], vela['volume'])
  for vela in velas200:
    valores200['open'] = np.append(valores200['open'], vela['open'])
    valores200['high'] = np.append(valores200['open'], vela['max'])
    valores200['low'] = np.append(valores200['open'], vela['min'])
    valores200['close'] = np.append(valores200['open'], vela['close'])
    valores200['volume'] = np.append(valores200['open'], vela['volume'])
  calculo_sma_200 = SMA(valores200, 200)
  calculo_sma_20 = SMA(valores, 20)


# Funcao que calcula tendencia: Ele faz o calculo pegando a vela atual, fazendo o valor de fechamento vezes o valor de fechamento da vela de qntVelas atras,
# calcula a diferença percentual entre as duas velas para ver se existe realmente uma diferença entre os 2 valores para evitar erros na verificacao
def obterTendencia(Iq, timeframe, qntVelas):
  # timeframe em minutos, def por padrao como 5
  # qntVelas def por padrao como 20
  # time.time() pega as velas atuais
  velas = Iq.get_candles(asset, timeframe, qntVelas, time.time()) # Em segundos
  ultimo = round(velas[0]['close'], 4)  # recebe as velas de fechamento e pega ate 4 casas decimais
  primeiro = round(velas[-1]['close'], 4) # pega a ultima vela de fechamento e pega ate 4 casas decimais

  diferenca = abs(round(((ultimo - primeiro) / primeiro) * 100, 3)) # calculo de diferenca percentual dos dois valores
  tendencia = "CALL" if ultimo < primeiro and diferenca > 0.01 else "PUT" if ultimo > primeiro and diferenca > 0.01 else False
  #print(tendencia)
  return tendencia


# Estrategia de SOROS com reset em caso de perca e aumento de venda/compra pelos lucros.
def obterSoros(Iq):
  entrada_base = 5
  soros_lucro = 0.0
  soros_porcentagem = round(80 / 100, 2) # definir qnts % do lucros sera usado no soros
  soros_niveis = 1
  soros_atual = 0
  while True:
    entrada = float(entrada_base)
    #verifica se tem lucro
    if soros_lucro > 0.0:
      # verifica se ainda da pra fazer soros pra nao fazer soros infinitamente
      if soros_atual <= soros_niveis:
        #se estiver dentro dos niveis, entao faz entrada
        entrada = round(entrada_base + (soros_lucro * soros_porcentagem), 2)
      else:
        # passou dos niveis de soros, entao reseta lucros e niveis
        soros_lucro = 0.0
        soros_atual = 0
    status, id = Iq.buy_digital_spot(asset, entrada, 'call', 1)

    if status:
      status = False
      while status == False:
        status, valor = Iq.check_win_digital_v2(id)

      if status:
        valor = round(valor, 2)
        if valor > 0:
          soros_lucro = valor
          soros_atual += 1
          print('WIN! +', valor)
        elif valor < 0:
          soros_lucro = 0.0
          soros_atual = 0
          print('LOSS! ', valor)
        else:
          print('EMPATE')


# Obter vela atual
def dadosVelaAtual(Iq, timeframe):
  #print("Obtendo vela atual");
  # timeframe em minutos, que é o periodo escolhido la no IQ Option para analise
  vela = Iq.get_candles(asset, timeframe, 1, time.time())   # em segundos
  
  return vela

# Obter varias velas (max ate 1000 velas)
def dadosVelas(Iq, timeframe, qntVelas):
  #print("Obtendo varias velas")
  # timeframe em minutos, que é o periodo escolhido la no IQ Option para analise
  # qntVelas: o total de velas que queremos retornar.
  #vela = Iq.get_candles(asset, int(timeframe *60), qntVelas, time.time())
  vela = Iq.get_candles(asset, timeframe, qntVelas, time.time()) # em segundos
  return vela

# Funcao para pegar os dados de velas e transformar em um dataframe
def get_with_dataframe(Iq, timeframe, qntVelas):
  df = pd.DataFrame()       # DataFrame vazio
  velas = []              # Array vazio de candles
  velas = Iq.get_candles(asset, timeframe, qntVelas, time.time())   # Chamada na IQ Option pra pegar os candles na data atual  # Em segundos
  df = pd.concat([pd.DataFrame(velas), df], ignore_index=True)            # Coloco os dados dos candles num dataframe
  return df


def dadosMaisMilVelas(Iq, timeframe, totMilhares):
  total = []
  tempo = time.time()
  # totMilhares: total de velas em 1000 vezes que irao ser retornadas. Se for 2 é 2000 velas, e assim por diante.
  for i in range(totMilhares):
    x = Iq.get_candles(asset, timeframe, 1000, tempo)    # Pega as velas # Em segundos
    total = x+total               # Add valores no array
    tempo = int(x[0]['from']) - 1 # Atualiza tempo que pega os dados para nao ficar retornando os mesmos 1000
  
  #print(len(total))

  for velas in total:
    print(timestamp_converter(velas['from']))


# Funcao para tentar pegar as velas em tempo real (preco altera em tempo real, que nao tem como ver horario de abertura e fechamento)!
def obterVelasTempoReal(Iq, timeframe, buffer):
  # buffer: o valor que queremos salvar/opter
  Iq.start_candles_stream(asset, int(timeframe *60), buffer)
  time.sleep(1)
  vela = Iq.get_realtime_candles(asset, int(timeframe *60))
  Iq.stop_candles_stream(asset, int(timeframe *60))
  # Retornando os dados em tempo real como um looping:
  while True:
    # Contornando a classe do objeto (classe dict) e pegar a informacao do estado da vela
    for velas in vela:
      print(vela[velas]['close'])
    time.sleep(1)


# Funcao para obter o RSI
def rsi_tradingview(ohlc: pd.DataFrame, period: int = 14, round_rsi: bool = True):
    """ Implements the RSI indicator as defined by TradingView on March 15, 2021.
        The TradingView code is as follows:
        //@version=4
        study(title="Relative Strength Index", shorttitle="RSI", format=format.price, precision=2, resolution="")
        len = input(14, minval=1, title="Length")
        src = input(close, "Source", type = input.source)
        up = rma(max(change(src), 0), len)
        down = rma(-min(change(src), 0), len)
        rsi = down == 0 ? 100 : up == 0 ? 0 : 100 - (100 / (1 + up / down))
        plot(rsi, "RSI", color=#8E1599)
        band1 = hline(70, "Upper Band", color=#C0C0C0)
        band0 = hline(30, "Lower Band", color=#C0C0C0)
        fill(band1, band0, color=#9915FF, transp=90, title="Background")
    :param ohlc:
    :param period:
    :param round_rsi:
    :return: an array with the RSI indicator values
    """

    delta = ohlc["close"].diff()

    up = delta.copy()
    up[up < 0] = 0
    up = pd.Series.ewm(up, alpha=1/period).mean()

    down = delta.copy()
    down[down > 0] = 0
    down *= -1
    down = pd.Series.ewm(down, alpha=1/period).mean()

    rsi = np.where(up == 0, 0, np.where(down == 0, 100, 100 - (100 / (1 + up / down))))

    return np.round(rsi, 2) if round_rsi else rsi


def tendenciaPorRSI(rsi):
  dentro_al = 0    # Dentro que esta no rango aceitavel para fazer parte da tendencia pra cima
  dentro_ba = 0    # Dentro que esta no rango aceitavel para fazer parte da tendencia pra baixo
  fora_al = 0      # Esta fora de fazer parte da tendencia pra cima
  fora_ba = 0      # Esta fora de fazer parte da tendencia pra baixo

  for i in range(len(rsi)):
    #print(f"RSI={rsi[i]}")
    # Pega so os 5 ultimos da lista
    if i >= 15:
      if rsi[i] <= 56.5:
        dentro_al += 1
      if rsi[i] > 56.5:
        fora_al += 1
      if rsi[i] >= 53.5:
        dentro_ba += 1
      if rsi[i] < 53.5:
        fora_ba += 1
  if dentro_al > dentro_ba:
    # Entao pode ser que tenhamos uma tendencia pra cima
    if dentro_al > fora_al:
      return "CALL"
    else:
      return False
  else:
    # Entao pode ser que tenhamos tendencia pra baixo
    if dentro_ba > fora_ba:
      return "PUT"
    else:
      return False


  
# Função que pega os dados tecnicos de um asset (nao funciona para -OTC)
def get_indicadores_tecnicos(Iq):
  # While true pra que a aplicação nunca morra (fique sendo executada a cada minuto)
  while True:
    # Obter dados tecnicos da corretora definida pelo asset
    indicators = Iq.get_technical_indicators(asset)
    # Separar dados tecnicos obtidos em periodos
    m1 = {}
    m5 = {}
    m15 = {}
    # Dicionado que vai pegar todos os indicadores tecnicos
    geral = {}
    # for pra fazer o loop dos indicadores recebidos
    for indicador in indicators:
      # Acessar as propriedades dentro dos indicadores
      v = indicador["action"]
      group = indicador["group"]
      candle_size = indicador["candle_size"]

      # Verifica se o grupo for de media movel
      if group == 'MOVING AVERAGES':
        # Identificar que esta no m1 (candles de 1min)
        if candle_size == 60:
          # Verificar se o valor já não foi adicionado no grupo
          if v not in m1:
            # Colocar o valor de v no m1 como 0 caso ele não existir
            m1[v] = 0
          # Caso existir, colocar o valor de v no m1 +1, que é pra somar o total de vezes que recebi o buy dentro de 1min
          m1[v] += 1
        # Identificar que esta no m5 (candles de 5min)
        if candle_size == 300:
          if v not in m5:
            m5[v] = 0
          m5[v] += 1
        # Identificar que esta no m15 (candles de 15min)
        if candle_size == 900:
          if v not in m15:
            m15[v] = 0
          m15[v] += 1
      # Todos os indicadores
      if v not in geral:
        geral[v] = 5
      geral[v] += 1


    # Tentar trabalhar com os valores retornados:
    # Condição simple para mostrar uma estratégia básica de compra ou venda
    # 1) Condição de compra pro m1. 
    if "buy" in m1 and "buy" in m5 and "buy" in m15:
      # Quero todos os buy das listas, e ver se temos os valores dentro desses dicionarios
      # Fazemos um trade simples na condição baseada dentro dos valores que podem vir dentro de cada tradeframe
      if m1['buy'] >= 16 and m5['buy'] >= 16 and m15['buy'] >= 16:
        # Executamos uma ordem de compra no iq options
        # Valor de compra de 4, tipo de corretora, call pra compra (se fosse venda seria sell), e duração de 1min
        Iq.buy(10, asset, 'call', 1)
        print("Foi realizada um trade de compra")
      
    time.sleep(3)

# Executa estrategia de trading que calcula RSI, tendencia de velas e media movel de 20 e 200
def estrategia_trading(Iq):
  totCall = 0
  totPut = 0
  try:
    # Faço loop infinito
    while True:
      if is_time_trade(Iq):
        print('\nAnalisando!')
        tendencia1 = obterTendencia(Iq, 5, 20)
        ohlc = get_with_dataframe(Iq, 5, 20)
        rsi = rsi_tradingview(ohlc)
        tendencia_rsi = tendenciaPorRSI(rsi)
        opened = ohlc['open']
        closed = ohlc['close']
        tendencia_maioria = maioria(opened, closed)
        tendencia_signal = mhi(opened, closed)

        # Analise de medias moveis
        velas = dadosVelas(Iq, 5, 20)
        velas100 = dadosVelas(Iq, 5, 100)
        velas200 = dadosVelas(Iq, 5, 200)
        
        valores = {
          'open': np.array([]),
          'high': np.array([]),
          'low': np.array([]),
          'close': np.array([]),
          'volume': np.array([])
        }

        valoresExp100 = {
          'open': np.array([]),
          'high': np.array([]),
          'low': np.array([]),
          'close': np.array([]),
          'volume': np.array([])
        }

        valores200 = {
          'open': np.array([]),
          'high': np.array([]),
          'low': np.array([]),
          'close': np.array([]),
          'volume': np.array([])
        }

        for vela in velas:
          valores['open'] = np.append(valores['open'], vela['open'])
          valores['high'] = np.append(valores['open'], vela['max'])
          valores['low'] = np.append(valores['open'], vela['min'])
          valores['close'] = np.append(valores['open'], vela['close'])
          valores['volume'] = np.append(valores['open'], vela['volume'])
        for vela in velas100:
          valoresExp100['open'] = np.append(valoresExp100['open'], vela['open'])
          valoresExp100['high'] = np.append(valoresExp100['open'], vela['max'])
          valoresExp100['low'] = np.append(valoresExp100['open'], vela['min'])
          valoresExp100['close'] = np.append(valoresExp100['open'], vela['close'])
          valoresExp100['volume'] = np.append(valoresExp100['open'], vela['volume'])
        for vela in velas200:
          valores200['open'] = np.append(valores200['open'], vela['open'])
          valores200['high'] = np.append(valores200['open'], vela['max'])
          valores200['low'] = np.append(valores200['open'], vela['min'])
          valores200['close'] = np.append(valores200['open'], vela['close'])
          valores200['volume'] = np.append(valores200['open'], vela['volume'])
        
        calculo_ema_100 = EMA(valoresExp100, 100)
        calculo_sma_200 = SMA(valores200, 200)
        calculo_sma_20 = SMA(valores, 20)
        medMovel20 = calculo_sma_20[-1]
        medMovel100 = calculo_ema_100[-1]
        medMovel200 = calculo_sma_200[-1]

        velaAtual = dadosVelaAtual(Iq, 1)
        valVela = velaAtual[0]['open']
        if medMovel20 > medMovel200 and valVela > medMovel20:
          # provavelmente é tendencia alcista
          totCall += 1
        if medMovel20 < medMovel200 and valVela < medMovel20:
          # provavelmente é tendencia baixa
          totPut += 1
        if medMovel20 > medMovel200 and valVela < medMovel20:
          # provavelmente ta em um soporte/resistencia ou ta mudando de tendencia
          totPut += 1
        if medMovel20 < medMovel200 and valVela > medMovel20:
          # provavelmente ta em um soporte/resistencia ou ta mudando de tendencia
          totCall += 1
        # Calc com media movel exponencial
        if medMovel100 < valVela:
          totCall += 1
        if medMovel100 > valVela:
          totPut += 1
        
        if tendencia_rsi == "CALL":
          totCall += 1
        if tendencia1 == "CALL":
          totCall += 1
        if tendencia_signal == "CALL":
          totCall += 1
        if tendencia_maioria == "CALL":
          totCall += 1
        if tendencia_rsi == "PUT":
          totPut += 1
        if tendencia1 == "PUT":
          totPut += 1
        if tendencia_signal == "PUT":
          totPut += 1
        if tendencia_maioria == "PUT":
          totPut += 1
        
        
        if totCall > totPut and totCall >= 2:
        #if totCall > totPut:
          # acao de compra
          print("Foi feita uma compra")
          order_check, order_id = Iq.buy(buy_amount, asset, "call", expirations_mode)
          # Função que pega os resultados vai validar e imprimir a resposta
          res = check_order(Iq, order_check, order_id)
          # Stop do robô caso ele atingir um dos limites
          stopsLoss(Iq)
          if res is not None:
            pay = payout(Iq)
            martingaleNew(Iq, res, "call")
        if totPut > totCall and totPut >= 2:
        #if totPut > totCall:
          # acao de venda
          print("Foi feita uma venda")
          order_check, order_id = Iq.buy(buy_amount, asset, "put", expirations_mode)
          # Função que pega os resultados vai validar e imprimir a resposta
          res = check_order(Iq, order_check, order_id)
          # Stop do robô caso ele atingir um dos limites
          stopsLoss(Iq)
          if res is not None:
            pay = payout(Iq)
            martingaleNew(Iq, res, "put")

        print("END CICLO")

        totCall = 0
        totPut = 0


      time.sleep(1)
  except Exception as e:
    #print("Server error - await 5 seconds: " + str(e))
    #print(traceback.format_exc())
    #time.sleep(3)
    print("Server error - await 5 seconds: " + str(e))
    #print("Parando robô")
    time.sleep(3)

# Função que executa o robô pedindo pro usuario logar a sua conta
def loginWithAccount():
  # Execução de login na api
  # Pedir pro usuário fazer login na sua conta na IQ Options, tendo até no máximo 3 tentativas
  try:
    try_login= 0
    Iq = {}
    status = False
    print("\n\nInforme seu usuário e senha para iniciar\n")
    while status == False and try_login < 3:
      username = input("Usuário: ")
      password = getpass.getpass("Senha: ")
      Iq = IQ_Option(username, password)
      try_login += 1
      # Iniciamos tentativa de conexão com a API
      status, reason = Iq.connect()

      if status == False:
        # Erro em login
        res = json.loads(reason)
        if "code" in res and res["code"] == "invalid_credentials":
          print("\n\nErro ao conectar: Usuário ou senha incorreta\n\n")
        else:
          print("\n\nErro ao tentar se conectar: " + res["message"] + "\n\n")
      else:
        # Login correto, quebra o while
        if reason == "2FA":
          print('##### Login de 2 autenticacoes #####')
          print("Digite o codigo enviado ao seu telefone por SMS")

          code_sms = input("digite o codigo: ")
          status, reason = Iq.connect_2fa(code_sms)

          print('##### Segunda autenticacao #####')
          print('Status:', status)
          print('Reason:', reason)
          print("Email:", Iq.email)
        break
    
    # Verifica se o login esta correto realmente
    if status == False:
      raise ValueError("Você excedeu 3 tentativas de login. Tente novamente mais tarde \n\n")

    # Se não cair no if, executa a mensagem:
    print("Conectado com sucesso")
    escolherMode()
    # Setamos tipo de conta que vamos a usar (real e praticas)
    Iq.change_balance(MODE)
    # Executa ações
    defAssetOpen(Iq)
    defMoneyValuesAccount(Iq)
    programarSinal()
    print(asset)
    estrategia_trading(Iq)

  # Terminar de validar o try
  except ValueError as ve:
    print(ve)
    print('Parando o bot')
  #except KeyBoardInterrupt:
  #  print("Parando bot")

loginWithAccount()