# encoder_interface.py
# Módulo para configurar y leer un encoder incremental vía QSB-S usando UART

import serial
import time
from typing import List, Optional

# Comandos básicos en formato bytes
COMMAND_MODE_QUADRATURE = b"W0000\r\n"
COMMAND_MDR0_X4_FREE = b"W0303\r\n"  # x4, free-running, índice deshabilitado
COMMAND_MDR1_ENABLE = b"W04000\r\n"  # contador habilitado, sin triggers, sentido up
COMMAND_CLEAR_CNTR = b"W092\r\n"      # borra CNTR a 0
COMMAND_THRESHOLD_0 = b"W0B0000\r\n"  # threshold = 0
COMMAND_INTERVAL_OFF = b"W0CFFFF\r\n"  # interval rate = 0xFFFF (streaming off)
COMMAND_EOR_SPACE_CR_LF = b"W15B\r\n"  # EOR bits: espacio + CR + LF
COMMAND_READ_ENCODER = b"R0E\r\n"    # lectura puntual de encoder

# Baud rates típicos para QSB-S (incluye default 230400)
DEFAULT_BAUDRATES = [9600, 19200, 38400, 57600, 115200, 230400]


def configure_encoder(port: str,
                      baudrate: int = 230400,
                      timeout: float = 0.5) -> serial.Serial:
    """
    Abre el puerto serie y configura el QSB en modo cuadratura ×4, free-running,
    sin índice, sin triggers y listo para lecturas puntuales.
    Limpia primero el mensaje de bienvenida que envía la QSB-S al conectarse.
    """
    ser = serial.Serial(port=port,
                        baudrate=baudrate,
                        bytesize=serial.EIGHTBITS,
                        parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE,
                        timeout=timeout,
                        rtscts=False,
                        xonxoff=False)
    # Esperar y descartar mensaje de bienvenida automático
    time.sleep(0.1)
    print(f'Mensaje de inicializacion: {ser.readline()}')           # consume "QSB-S 0E!<CR><LF>"
    ser.reset_input_buffer() # limpia cualquier otro dato residual

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
        ser.write(cmd)
        time.sleep(0.05)
        response = ser.readline()
        if not response or not response.startswith(b'w'):
            ser.close()
            raise IOError(f"Error al configurar: comando {cmd.strip()} no confirmado. Recibido: {response}")

    return ser



def read_encoder(ser: serial.Serial) -> int:
    """
    Envía el comando de lectura puntual y devuelve el valor entero del contador.

    :param ser: Objeto serial.Serial ya configurado.
    :return: Valor actual de CNTR (int).
    """
    ser.reset_input_buffer()
    ser.write(COMMAND_READ_ENCODER)
    time.sleep(0.02)
    line = ser.readline().decode('ascii', errors='ignore').strip()
    parts = line.split()
    if len(parts) < 3 or parts[0] != 'r':
        raise ValueError(f"Respuesta inesperada al leer encoder: '{line}'")

    count_hex = parts[2]
    try:
        return int(count_hex, 16)
    except ValueError:
        raise ValueError(f"No se pudo convertir '{count_hex}' a entero")


def detect_baudrate(port: str,
                    baudrates: Optional[List[int]] = None,
                    timeout: float = 0.5) -> int:
    """
    Detecta automáticamente la velocidad de comunicación UART a la que responde el QSB.

    :param port: Ruta del dispositivo UART.
    :param baudrates: Lista de baudios a probar (por defecto DEFAULT_BAUDRATES).
    :param timeout: Timeout de lectura en segundos para cada prueba.
    :return: Baudrate detectado.
    :raises RuntimeError: Si no se detecta respuesta en ninguno de los baudios.
    """
    if baudrates is None:
        baudrates = DEFAULT_BAUDRATES

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
                print(f'Testeo de {rate}bauds exitoso -> Respuesta: {response}')
                return rate
        except (serial.SerialException, IOError):
            continue
    print("No se detectó respuesta en los baudios probados.")











#-----------------------------

# ==================== CLASE WRAPPER PARA INTEGRACIÓN ====================

class EncoderInterface:
    """Clase wrapper para facilitar integración con la aplicación."""

    def __init__(self):
        self.serial_connection = None
        self.port = None
        self.baudrate = None
        self.is_connected = False
        self.initial_count = None

    def connect(self, port: str) -> bool:
        """
        Conecta al encoder en el puerto especificado.
        Detecta automáticamente el baudrate y configura el encoder.

        Args:
            port (str): Puerto COM del encoder

        Returns:
            bool: True si la conexión fue exitosa
        """
        try:
            # Detectar baudrate automáticamente
            print(f"[Enc-Config] -> Detectando baudrate en puerto {port}...")
            self.baudrate = detect_baudrate(port)
            print(f"[Enc-Config] -> Baudrate detectado: {self.baudrate}")

            # Configurar encoder
            print("[Enc-Config] -> Configurando encoder...")
            self.serial_connection = configure_encoder(port, self.baudrate)

            self.port = port
            self.is_connected = True
            self.initial_count = None  # Se establecerá en la primera lectura

            print("[Enc-Config] -> ✅ Encoder configurado correctamente")
            return True

        except Exception as e:
            print(f"[Enc-Config] -> ❌ Error conectando encoder: {e}")
            self.disconnect()
            return False

    def disconnect(self):
        """Desconecta el encoder."""
        if self.serial_connection:
            try:
                self.serial_connection.close()
            except Exception as e:
                print(f"[Enc-Config] -> Error cerrando conexión: {e}")
            finally:
                self.serial_connection = None

        self.is_connected = False
        self.port = None
        self.baudrate = None
        self.initial_count = None

    def read_position_mm(self) -> Optional[float]:
        """
        Lee la posición actual del encoder en milímetros.

        Returns:
            Optional[float]: Posición en mm desde el punto de referencia, o None si hay error
        """
        if not self.is_connected or not self.serial_connection:
            return None

        try:
            # Leer contador actual
            current_count = read_encoder(self.serial_connection)

            # Establecer referencia en primera lectura
            if self.initial_count is None:
                self.initial_count = current_count
                return 0.0

            # Calcular desplazamiento desde referencia
            delta_counts = current_count - self.initial_count
            position_mm = delta_counts * ENCODER_RESOLUTION

            return position_mm

        except Exception as e:
            print(f"[Enc-Func] -> Error leyendo encoder: {e}")
            return None

    def reset_position(self):
        """Reinicia la posición de referencia del encoder."""
        if self.is_connected and self.serial_connection:
            try:
                # Leer posición actual y establecerla como nueva referencia
                current_count = read_encoder(self.serial_connection)
                self.initial_count = current_count
                print("[Enc-Func] -> Posición del encoder reiniciada")
            except Exception as e:
                print(f"[Enc-Func] -> Error reiniciando posición: {e}")

    def get_info(self) -> dict:
        """
        Obtiene información de configuración del encoder.

        Returns:
            dict: Información del encoder
        """
        return {
            'connected': self.is_connected,
            'port': self.port,
            'baudrate': self.baudrate,
            'resolution_mm_per_pulse': ENCODER_RESOLUTION,
            'mode': 'Cuadratura x4, Free-running'
        }



# ==================== FUNCIONES DE UTILIDAD ====================

def test_encoder_connection(port: str) -> bool:
    """
    Prueba la conexión con el encoder sin configurarlo.

    Args:
        port (str): Puerto COM a probar

    Returns:
        bool: True si se detecta el encoder
    """
    try:
        detect_baudrate(port)
        return True
    except (RuntimeError, Exception):
        return False