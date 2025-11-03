import spidev
import time
import logging
import csv
from datetime import datetime
from typing import Tuple

# Configuración de logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Constantes SPI
SPI_BUS = 0            # Bus SPI0
SPI_DEVICE = 0         # CE0
SPI_CLOCK_HZ = 200_000 # 300 kHz
SPI_MODE = 0b11        # CPOL=1, CPHA=1 (modo 3)

# Direcciones de registro
PRODUCT_ID_ADDR = 0x00
PRODUCT_ID_VAL = 0x31
STATUS_REG = 0x02
REG_X_L = 0x03
REG_X_H = 0x11
REG_Y_L = 0x04
REG_Y_H = 0x12

# Máscaras y parámetros de polling
MSB_MASK = 0x80        # Máscara para extraer el bit 7
POLL_INTERVAL = 0.008  # 8 ms
DEFAULT_TIMEOUT = 600.0 # 60 segundos

class SpiSensor:
    def __init__(self, bus = SPI_BUS, device = SPI_DEVICE):
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = SPI_CLOCK_HZ
        self.spi.mode = SPI_MODE
        logging.info(f"SPI abierto en bus {bus}, dispositivo {device}, modo {SPI_MODE}")

    def read_register(self, address):
        if not 0 <= address <= 0x7F:
            raise ValueError(f"Dirección inválida: 0x{address:02X}")
        cmd = address & 0x7F
        resp = self.spi.xfer2([cmd, 0x00])
        return resp[1]

    def write_register(self, address, value):
        if not 0 <= address <= 0x7F:
            raise ValueError(f"Dirección inválida: 0x{address:02X}")
        if not 0 <= value <= 0xFF:
            raise ValueError(f"Valor inválido: 0x{value:02X}")
        cmd = 0x80 | (address & 0x7F)
        self.spi.xfer2([cmd, value])

    def initialize(self, timeout = DEFAULT_TIMEOUT):
        start = time.time()
        while True:
            pid = self.read_register(PRODUCT_ID_ADDR)
            if pid == PRODUCT_ID_VAL:
                logging.info(f"Product ID válido: 0x{pid:02X}")
                return
            if time.time() - start > timeout:
                raise TimeoutError(f"Product ID inválido tras {timeout:.2f}s: 0x{pid:02X}")
            time.sleep(POLL_INTERVAL)

    def is_motion_status_on(self):
        ms = self.read_register(STATUS_REG)
        return bool(ms & MSB_MASK)

    def read_sensor(self, timeout = DEFAULT_TIMEOUT):
        start = time.time()
        while not self.is_motion_status_on():
            if time.time() - start > timeout:
                return 0,0
            time.sleep(POLL_INTERVAL)
        x_l = self.read_register(REG_X_L)
        x_h = self.read_register(REG_X_H)
        y_l = self.read_register(REG_Y_L)
        y_h = self.read_register(REG_Y_H)
        raw_x = (x_h << 8) | x_l
        raw_y = (y_h << 8) | y_l
        x = raw_x - (1 << 16) if (raw_x & (1 << 15)) else raw_x
        y = raw_y - (1 << 16) if (raw_y & (1 << 15)) else raw_y
        return x, y

    def read_continuous(self, factor_x = 1.0, factor_y = 1.0, save_csv = False):
        x_sum = 0.0
        y_sum = 0.0
        records = []  # Lista de tuplas para CSV
        logging.info("Inicio de lectura continua calibrada (Ctrl+C para detener)")
        _,_ = self.read_sensor() # Vacio el buffer del sensor
        try:
            while True:
                raw_x, raw_y = self.read_sensor()
                delta_x = raw_x * factor_x
                delta_y = raw_y * factor_y
                x_sum += delta_x
                y_sum += delta_y
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                records.append((timestamp, delta_x/1000, delta_y/1000, x_sum/1000, y_sum/1000))
                print(f"\r{timestamp} | ΔX={delta_x/1000:.3f}, ΔY={delta_y/1000:.3f} | SumX={abs(x_sum/1000):.3f}, SumY={abs(y_sum/1000):.3f}  ", end="", flush=True)
        except KeyboardInterrupt:
            logging.info("Lectura continua detenida por usuario")
            if save_csv:
                # Guardar CSV
                now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"LecturasCSV/PAT9130/{now_str}-{factor_x:.3f}-{factor_y:.3f}.csv"
                with open(filename, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['timestamp', 'delta_x', 'delta_y', 'acumulado_x', 'acumulado_y'])
                    writer.writerows(records)
                logging.info(f"Datos guardados en {filename}")
        return x_sum/1000, y_sum/1000 # divido por 1000 para pasar a mm

    def calibrate_x(self, known_distance_x):
        _,_ = self.read_sensor() # Para vaciar el buffer
        input(f"Listo para calibrar X. Mueve el sensor {known_distance_x/1000}mm y pulsa Enter.")
        raw_x, _ = self.read_sensor()
        factor_x = known_distance_x / raw_x if raw_x else 1.0
        logging.info(f"Raw X medido: {raw_x} -> Factor X: {factor_x:.6f}")

        return factor_x

    def calibrate_y(self, known_distance_y):
        _,_ = self.read_sensor() # Para vaciar el buffer
        input(f"Listo para calibrar Y. Mueve el sensor {known_distance_y/1000}mm y pulsa Enter.")
        _, raw_y = self.read_sensor()
        factor_y = known_distance_y / raw_y if raw_y else 1.0
        logging.info(f"Raw Y medido: {raw_y} -> Factor y: {factor_y:.6f}")

        return factor_y
    

if __name__ == "__main__":
    sensor = SpiSensor()
    sensor.initialize()

    # -------- Etapa de calibración
    fx = sensor.calibrate_x(known_distance_y=15000) #15000 um = 15mm
    fy = sensor.calibrate_y(known_distance_y=15000) #15000 um = 15mm

    # -------- Etapa de lectura continua y guardado CSV
    _,_ = sensor.read_sensor() # Vacio el buffer del sensor
    for i in range(1): # N° de mediciones a realizar
        print(f'Iteración: {i}')
        x_total, y_total = sensor.read_continuous(factor_x=fx, factor_y=fy, save_csv=True)
        logging.info(f"Desplazamiento total  → X: {x_total:.3f}, Y: {y_total:.3f}     ")
  