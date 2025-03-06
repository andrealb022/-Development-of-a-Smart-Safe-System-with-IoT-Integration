from umqtt.simple import MQTTClient
from machine import Pin, PWM,SoftI2C,ADC
import ssd1306
import framebuf
from time import sleep_ms
import tsl2561
import time
import network
import dht
import ujson

#Definizione classe per il sensore a infrarossi
class LDR:
    def __init__(self, pin, min_value=0, max_value=10):

        if min_value >= max_value:
            raise Exception('Min value is greater or equal to max value')

        # initialize ADC (analog to digital conversion)
        # create an object ADC
        self.adc = ADC(Pin(pin))
        self.min_value = min_value
        self.max_value = max_value

    def read(self):
        return self.adc.read()

    def value(self):
        return (self.max_value - self.min_value) * self.read() / 4095

#Definizione classe Buzzer
class BUZZER:
    def __init__(self, sig_pin):
        self.pwm = PWM(Pin(sig_pin, Pin.OUT))
        self.pwm.duty(0)
        
    def play(self, melodies, wait, duty):
        mostraMessaggio("ALLARME ATTIVATO!")
        for note in melodies:
            if note == 0:
                self.pwm.duty(0)
            else:
                self.pwm.freq(note)
                self.pwm.duty(duty)
                segnala_errore()
                sleep_ms(wait)
        self.pwm.duty(0)
        pulisci_schermo()
#Suono Allarme        
A6=1760
allarme = [
    A6, A6, 0, A6, A6, 0,
    A6, A6, 0,
    ]

#Parametri connessione MQTT
MQTT_CLIENT_ID = "Utente1"
MQTT_BROKER    = "test.mosquitto.org"
MQTT_USER      = ""
MQTT_PASSWORD  = ""

#Connessione al wifi
print("Connecting to WiFi", end="")
sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)
sta_if.connect('iPhone di Alberto','alberto1')
while not sta_if.isconnected():
  print(".", end="")
  time.sleep(0.1)
print(" Connected!")

# Funzione di callback chiamata quando viene ricevuto un messaggio MQTT
def callback(topic,msg):
    global client
    # Azione in base al topic
    if (topic == b'codice/sblocco'):
        msg_text = msg.decode('utf-8')  # Decodifica il messaggio come testo UTF-8
        data = ujson.loads(msg_text)  # Carica il testo JSON in un oggetto Python
        if 'code' in data:
            codice_sblocco = data['code']
        controllo_apertura(client,codice_sblocco)
        
    elif (topic == b'cambio/codice'):
        msg_text = msg.decode('utf-8')  # Decodifica il messaggio come testo UTF-8
        data = ujson.loads(msg_text)  # Carica il testo JSON in un oggetto Python
        if 'old_code' in data:
            codice_vecchio = data['old_code']
        if 'new_code' in data:
            codice_nuovo= data['new_code']
        cambia_codice(client,codice_vecchio,codice_nuovo)
         
    elif (topic == b'chiudi/cassa'):
        chiudi_cassaforte(client)
    
    elif(topic==b'verifica/oggetto'):
        pubblica_presenza_oggetto(client)
        
def pubblica_presenza_oggetto(client):
    if(verifica_presenza_oggetto()):
        client.publish("Presenza Oggetto","Oggetto presente")
        mostraMessaggio("Oggetto presente!")
        time.sleep(3)
        pulisci_schermo()
    else:
        client.publish("Presenza Oggetto","Oggetto non presente")
        mostraMessaggio("Oggetto non presente!")
        time.sleep(3)
        pulisci_schermo()
        
def verifica_presenza_oggetto():
    global sensore_lux
    if(sensore_lux.read() < 0.7):
        return True
    else:
        return False
        

def pulisci_schermo():
    global display
    display.fill(0)            #pulisco lo schermo mostrando uno sfondo nero
    display.show()
    
#Funzione per la verifica del codice e l'apertura
def controllo_apertura(client,codice_sblocco):
    global unlock_code
    global count_error
    if(codice_sblocco == unlock_code):
        count_error=0
        apri_cassaforte(client)
        segnala_ok()
    else:
        client.publish("Codice non valido","Inserire codice corretto")
        mostraMessaggio("Codice errato RIPROVA!")
        time.sleep(3)
        pulisci_schermo()
        count_error=count_error+1
        if(count_error == 3):
            suona_allarme("Codice sbagliato 3 volte!")
            count_error=0

#Funzione per cambiare il codice di sblocco
def cambia_codice(client,codice_vecchio,codice_nuovo):
    global unlock_code
    if(codice_vecchio == unlock_code):
            if(codice_vecchio == codice_nuovo):
                client.publish("Codice non valido", "Inserire un codice nuovo diverso da quello attuale")
                segnala_errore()
            else:
                unlock_code = codice_nuovo
                client.publish("Codice aggiornato","Il codice è stato aggiornato con successo!")
                segnala_ok()
                mostraMessaggio("Codice aggiornato")
                time.sleep(3)
                pulisci_schermo()
    else:
        client.publish("Codice non valido","Il codice vecchio non corrisponde a quello attuale!")
        segnala_errore()

#Funzione che attiva l'allarme
def suona_allarme(str):
    global buzzer
    global client
    client.publish("ALLARME",str)
    buzzer.play(allarme,600,512)
    

def segnala_errore():
    global ledRed
    ledRed.on()
    time.sleep(1)
    ledRed.off()
    
def segnala_ok():
    global ledGreen
    ledGreen.on()
    time.sleep(2)
    ledGreen.off()
    

#funzione che modifica l'angolo del motore, modificando il duty
def set_angle(angle,motore_servo):
    duty_min = 26
    duty_max = 123
    motore_servo.duty(int(duty_min + (angle/180)*(duty_max-duty_min)))

#funzione per aprire la cassaforte
def apri_cassaforte(client):
    global motore_servo
    global aperto
    if(aperto==False):
        set_angle(40,motore_servo) #imposto aperto (20 gradi)
        mostraMessaggio("Cassaforte sbloccata!")
        aperto=True
        client.publish("Codice valido","APERTURA CASSAFORTE...")
        segnala_ok()
    else:
        client.publish("ERRORE!","CASSAFORTE GIà APERTA")
    
#funzione per chiudere la cassaforte
def chiudi_cassaforte(client):
    global aperto
    global motore_servo
    if(aperto==True):
        set_angle(180,motore_servo) #chiude(180 gradi)
        mostraMessaggio("Cassaforte bloccata!")
        client.publish("Chiusura effettuata","Chiusura effettuata con successo")
        segnala_ok()
        aperto=False #imposto la cassaforte chiusa
        time.sleep(2)
        pulisci_schermo()
        
    else:
        client.publish("ERRORE!","Cassaforte chiusa")

def check_intrusione():
    global presente
    global sensore_infrarossi
    if(presente):
        if(presente != verifica_presenza_oggetto()):
                suona_allarme("Oggetto spostato!")
                if(verifica_presenza_oggetto()):
                    presente = verifica_presenza_oggetto()
    if(sensore_infrarossi.value()<8):
        suona_allarme("Rilevato movimento!")

def mostraMessaggio(str):
    global display
    pulisci_schermo()
    text_width = len(str) * 4  
    x = (display.width - text_width) // 2 #calcolo la x dove le scritte devono partire
    parole = str.split()     #divido la scritta in parole
    y = 45//len(parole)      #calcolo la y

    for parola in parole:
        display.text(parola, x, y)   
        display.show()       #mostro le parole
        y += 10
    
#connessione al broker e iscrizione ai topic
print("Connecting to MQTT server... ", end="")
client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER)
client.set_callback(callback)
client.connect()
client.subscribe('codice/sblocco')
client.subscribe('cambio/codice')
client.subscribe('chiudi/cassa')
client.subscribe('verifica/oggetto')
print("Connected!")

#inizializzo i Pin
aperto=False #variabile per sapere se la cassaforte è aperta
motore_servo = PWM(Pin(23), freq=50)
set_angle(180,motore_servo) #imposto la cassaforte chiusa di default(180 gradi)
i2c=SoftI2C(sda=Pin(16),scl=Pin(17))
sensore_lux=tsl2561.TSL2561(i2c)  #sensore di luminosità ambientale
presente=verifica_presenza_oggetto()  #vedo se all'inizio l'oggetto è presente
count_error=0 #variabile per il conteggio degli errori del codice
unlock_code="0000" #codice di sblocco inizialmente settati a "0000"
buzzer= BUZZER(22)        #buzzer per allarmi
ledRed = Pin(26,Pin.OUT)    #led rosso
ledRed.off()
ledGreen = Pin(27,Pin.OUT)   #led verde
ledGreen.off()
ledWhite = Pin(4,Pin.OUT)  #led bianco sempre attivo all'interno
ledWhite.on()
sensore_infrarossi=LDR(34)    #sensore ad infrarossi per il movimento
i2c = SoftI2C(sda=Pin(18), scl=Pin(19))
display = ssd1306.SSD1306_I2C(128, 64, i2c)
display.fill(0)
display.show()
# Mantieni il programma in esecuzione
try:
    while True:
        client.check_msg()    #controllo i messaggi
        if(not aperto):        #quando la cassaforte è chiusa attivo i controlli di sicurezza
            check_intrusione()
        else:
            presente = verifica_presenza_oggetto()

except KeyboardInterrupt:
    pulisci_schermo()
    set_angle(180,motore_servo) #imposto la cassaforte chiusa di default(180 gradi)
    ledWhite.off()
