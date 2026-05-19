import re
import socket
import subprocess


# Validacao dos números
def ip_valido(ip):
    padrao = r"^(?:\d{1,3}\.){3}\d{1,3}$"

    if not re.match(padrao, ip):
        return False
    for bloco in ip.split("."):
        numero = int(bloco)
        
        if numero < 0 or numero > 255:
            return False
    return True


# Traduiz o hostname pra número de ip
def traduzir_hostname(hostname):
    try:
        return socket.gethostbyname(hostname)
    except:
        return None


# Ping na impressora
def ping_host (host, time_espera = 1200):

    cmd = ["ping", "-n", "1", "-w", str(time_espera), host]

    comando = subprocess.run(
        cmd, 
        capture_output = True,
        text = True,
        check = False
    )
    
    return comando.returncode == 0

# Testando conexao TCP / Porta
def teste_porta_tcp(host, porta, timeoutb = 2.0):
    try:

        with socket.create_connection(
            (host, porta),
            timeout = timeoutb
        ):
            return True
        
    except OSError:
        return False


