# Módulo para configurar y leer un encoder incremental vía QSB-S usando UART

import serial
import time
from typing import List, Optional

# ==================== CONSTANTES DE CONFIGURACIÓN ====================
# Configuración del encoder
ENCODER_RESOLUTION = 0.01  # mm por pulso del encoder 

# Comandos básicos en formato bytes
COMMAND_MODE_QUADRATURE = b"W0000\r\n"
COMMAND_MDR0_X4_FREE = b"W0303\r\n"  # x4, free-running, índice deshabilitado
COMMAND_MDR1_ENABLE = b"W04000\r\n"  # contador habilitado, sin triggers, sentido up
COMMAND_CLEAR_CNTR = b"W092\r\n"  # borra CNTR a 0
COMMAND_THRESHOLD_0 = b"W0B0000\r\n"  # threshold = 0
COMMAND_INTERVAL_OFF = b"W0CFFFF\r\n"  # interval rate = 0xFFFF (streaming off)
COMMAND_EOR_SPACE_CR_LF = b"W15B\r\n"  # EOR bits: espacio + CR + LF
COMMAND_READ_ENCODER = b"R0E\r\n"  # lectura puntual de encoder

DEFAULT_BAUDRATES = [9600, 19200, 38400, 57600, 115200, 230400]


def configure_encoder(port: str, baudrate: int = 230400, timeout: float = 0.5) -> serial.Serial:
    print("[Enc-Func] -> Configurando encoder")
    last_exception = None
    ser = None

    for attempt in range(6):
        try:
            ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=timeout,
                rtscts=False,
                xonxoff=False
            )
            time.sleep(0.1)
            print(f'Conexión exitosa en el intento {attempt}')
            break
        except Exception as e:
            last_exception = e
            print(f"[ERROR] Falló al abrir {port} (intento {attempt+1}/6): {e}")
            time.sleep(0.1)

    if ser is None:
        raise last_exception

    # Secuencia de configuración habitual
    commands = [
        COMMAND_MODE_QUADRATURE,
        COMMAND_MDR0_X4_FREE,
        COMMAND_MDR1_ENABLE,
        COMMAND_CLEAR_CNTR,
        COMMAND_THRESHOLD_0,
        COMMAND_INTERVAL_OFF,
        COMMAND_EOR_SPACE_CR_LF
    ]
    for cmd in commands:
        ser.reset_input_buffer()  # limpia cualquier otro dato residual
        ser.write(cmd)
        time.sleep(0.05)
        response = ser.readline()
        print(f"[Enc-Config] -> Comando: {cmd.strip()} | Respuesta: {response}")

    return ser

def clear_encoder(ser: serial.Serial) -> None:
    ser.reset_input_buffer()  # limpia cualquier otro dato residual
    ser.write(COMMAND_CLEAR_CNTR)
    time.sleep(0.05)
    response = ser.readline()
    if not response or not response.startswith(b'w'):
        ser.close()
        raise IOError(f"Error al configurar: comando {COMMAND_CLEAR_CNTR} no confirmado. Recibido: {response}")
    return

def read_encoder(ser: serial.Serial) -> int:
    print("[Enc-Func] -> Leyendo encoder")
    ser.reset_input_buffer()
    ser.write(COMMAND_READ_ENCODER)
    time.sleep(0.02)
    line = ser.readline().decode('ascii', errors='ignore').strip()
    parts = line.split()
    if len(parts) < 3 or parts[0] != 'r':
        raise ValueError(f"Respuesta inesperada al leer encoder: '{line}'")

    count_hex = parts[2]
    try:
        return unsigned_to_signed(int(count_hex, 16))
    except ValueError:
        raise ValueError(f"No se pudo convertir '{count_hex}' a entero")

def unsigned_to_signed(val: int) -> int:
    """Convierte un entero de 32 bits sin signo a signo (int32)."""
    return val - 2**32 if val >= 2**31 else val

def detect_baudrate(port: str,timeout: float = 0.5) -> int:
    print("[Enc-Func] -> Detectando baudrate")
    baudrates = DEFAULT_BAUDRATES

    for i in range(2):
        for rate in baudrates:
            try:
                ser = serial.Serial(port=port,
                                    baudrate=rate,
                                    bytesize=serial.EIGHTBITS,
                                    parity=serial.PARITY_NONE,
                                    stopbits=serial.STOPBITS_ONE,
                                    timeout=timeout,
                                    rtscts=False,
                                    xonxoff=False)
                time.sleep(0.1)
                response = ser.readline()
                ser.close()
                if response == b'QSB-S  0E!\r\n':
                    print(f'---> Testeo de {rate} bauds Exitoso -> Respuesta: {response}')
                    return rate
                else:
                    print(f'---> Testeo de {rate} bauds -> Respuesta: {response}')
            except (ser.SerialException, IOError):
                continue
            finally:
                ser.close()

