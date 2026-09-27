import time
import random
import sys
from pypresence import Presence

# -------------------------------------------------------------
# CONFIGURACIÓN
# -------------------------------------------------------------
CLIENT_ID = "1402418696126992445"

# MODO OFICIAL ESTÁNDAR:
# - True: Muestra el logo oficial de League of Legends + tiempo transcurrido.
# - False: Modo detallado con campeón, mapa y rango.
MODO_OFICIAL_ESTANDAR = True

# Logo oficial de League of Legends (CDN oficial de Discord)
LOL_LOGO_URL = "https://cdn.discordapp.com/app-icons/1402418696126992445/7c99428541032ac02ec6981d88b78fb7.png?size=512"

# Duración aleatoria de cada partida (en minutos) antes de reiniciar a 00:00
DURACION_MINUTOS_MIN = 20
DURACION_MINUTOS_MAX = 30

# Opciones para el modo detallado (si MODO_OFICIAL_ESTANDAR = False)
DETAILS = "En partida"
STATE = "Grieta del Invocador (Clasificatoria)"
CHAMP_IMAGE = "https://ddragon.leagueoflegends.com/cdn/14.1.1/img/champion/Malzahar.png"
CHAMP_TEXT = "Malzahar"
RANK_IMAGE = "https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-shared-components/global/default/gold.png"
RANK_TEXT = "Oro II"

# -------------------------------------------------------------
def update_presence(rpc, start_time):
    if MODO_OFICIAL_ESTANDAR:
        rpc.update(
            start=start_time,
            large_image=LOL_LOGO_URL,
            large_text="League of Legends"
        )
    else:
        rpc.update(
            details=DETAILS,
            state=STATE,
            start=start_time,
            large_image=CHAMP_IMAGE,
            large_text=CHAMP_TEXT,
            small_image=RANK_IMAGE,
            small_text=RANK_TEXT
        )

def main():
    if CLIENT_ID == "TU_APPLICATION_ID_AQUI" or not CLIENT_ID.strip().isdigit():
        print("\n❌ Error: Debes colocar un Client ID válido en CLIENT_ID.\n")
        sys.exit(1)

    print("🔌 Conectando con Discord...")
    try:
        rpc = Presence(CLIENT_ID)
        rpc.connect()
        print("✅ ¡Conectado exitosamente con Discord!")

        while True:
            # Calcular duración de esta partida (en segundos)
            duracion_min = random.randint(DURACION_MINUTOS_MIN, DURACION_MINUTOS_MAX)
            duracion_seg = duracion_min * 60
            start_time = int(time.time())

            update_presence(rpc, start_time)
            print(f"🎮 Nueva partida iniciada. Durará ~{duracion_min} minutos antes de reiniciarse.")

            # Esperar a que concluya la partida
            tiempo_transcurrido = 0
            while tiempo_transcurrido < duracion_seg:
                time.sleep(15)
                tiempo_transcurrido = int(time.time()) - start_time

            print("🔄 Partida finalizada. Reiniciando contador a 00:00 para la siguiente partida...")
            # Breve pausa realista entre partidas (10 segundos)
            time.sleep(10)

    except KeyboardInterrupt:
        print("\n🛑 Deteniendo presencia...")
        if 'rpc' in locals():
            rpc.clear()
            rpc.close()
        print("Listo. ¡Hasta luego!")
    except Exception as e:
        print(f"❌ Error al conectar con Discord: {e}")

if __name__ == "__main__":
    main()
