

import time
from encoder_interface import detect_baudrate, configure_encoder, read_encoder

def test_detect_and_read(port: str):
    # 1. Detectar baudrate
    baud = detect_baudrate(port)

    # 2. Configurar encoder con el baud detectado
    ser = configure_encoder(port, baudrate=baud, timeout=0.5)
    print("Encoder configurado correctamente.")

    # 3. Prueba de lecturas a 20 Hz
    for i in range(100):
        val = read_encoder(ser)
        print(f"Lectura {i+1}: {val}")
        time.sleep(0.05)

    # 4. Cerrar puerto
    ser.close()
    print("Puerto cerrado. Test finalizado.")

if __name__ == '__main__':
    test_detect_and_read('COM3')  # Ajusta el puerto según tu sistema
