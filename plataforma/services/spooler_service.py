from __future__ import annotations
from ..models import Resultado_Operacao
from ..config import CONFIG
from pathlib import Path
import subprocess
import shutil


class SpoolerService:
    def __init__(self):
        self.pasta_spooler = Path(CONFIG.pasta_impressora)

    def _run_sc(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["sc", *args], capture_output=True, text=True, check=False, timeout=30
        )

    def verifica_spooler(self):
        comando = self. _run_sc(["query" , "Spooler"])
        output = (comando.stdout or "" ) + (comando.stderr or "")
        return "RUNNING" in output.upper()
    
    def parar_spooler(self):
        comando = self._run_sc(["net", "stop", "spooler"])
        if comando.returncode != 0:
            mensagem = f"Falha ao interromper spooler: {comando.stderr.strip()}"
            return Resultado_Operacao(False, mensagem)
        return Resultado_Operacao(True, "Spooler Interrompido!")
    
    def iniciar_spooler(self):
        comando = self._run_sc(["net", "start", "Spooler"])
        if comando.returncode != 0:
            mensagem = f"Falha ao iniciar Spooler: {comando.stderr.strip()}"
            return Resultado_Operacao(False, mensagem)
        return Resultado_Operacao(True, "Spooler iniciado!")
    
    def limpa_spooler(self):
        try:
            self.pasta_spooler.mkdir(parents=True, exist_ok=True)
            for arquivo in self.pasta_spooler.iterdir():
                if arquivo.is_dir():
                    shutil.rmtree(arquivo, ignore_errors= True)
                else:
                    arquivo.unlink(missing_ok=True)
            return Resultado_Operacao(True, "Fila de Spooler limpa!")
        except Exception as falha:
            mensagem = f"Falha ao excluir arquivos de Spooler: {falha}"
            return Resultado_Operacao(False,mensagem)

    def Resetar_spooler(self):
        stop = self.parar_spooler()
        if not stop.success:
            return stop
        clear = self.limpa_spooler()
        start = self.iniciar_spooler()
        success = clear.success and start.success and self.verifica_spooler()
        mensagem = "Reinicialização do Spooler Concluida." if success else "Reinicialização do spooler incompleta. "
        return Resultado_Operacao(
            success,
            mensagem,
            details = {
                "Stop": stop.message,
                "claer": clear.message,
                "start": start.message,
                "running": self.verifica_spooler(),
            },
        )
