import queue
import threading
import tkinter.messagebox as messagebox
from datetime import datetime
import customtkinter as ctk

from ..logger import build_logger
from ..models import Resultado_Operacao
from ..services.AutoFix import Auto_fix
from ..services.diagnostic import DiagnosticsService
from ..services.printer_service import PrinterService
from ..services.spooler_service import SpoolerService
from ..utilitarios.admin import is_admin
from .tema import setup_tema

class PrinterSupportApp:
    def __init__(self):
        setup_tema()
        self.logger = build_logger('Interface')
        self.printer_service = PrinterService()
        self.spooler_service = SpoolerService()
        self.diagnostics_service = DiagnosticsService()
        self.auto_fix = Auto_fix()
        self.log_queue = queue.Queue()
        
        self.root = ctk.CTk()
        self.root.title("Printer Support - Casa Nova Locadora")
        self.root.geometry("1020x560")
        self.root.minsize(920,560)
        
        self.selecionar_impressora = ctk.StringVar()
        self.valor_ip = ctk.StringVar()
        self.nome_driver = ctk.StringVar(value="Generic / Text Only")
        self.situacao_status = ctk.StringVar(value="Status: Pronto")
        self.menu_instalacao = self._build_fast_reinstall_options()
        
        self._build_ui()
        self._refresh_printers()
        self.root.after(250, self._kill_fila_log)
            
    def _build_ui(self):
        self.root.grid_columnconfigure(1, weight = 1)
        self.root.grid_rowconfigure(0, weight= 1)
        
        sidebar = ctk.CTkFrame(self.root, width= 300, corner_radius= 12)
        sidebar.grid(row = 0, column = 0, sticky = "nsew", padx = 12, pady = 12)
        sidebar.grid_columnconfigure(0, weight= 1)
        
        titulo = ctk.CTkLabel(
            sidebar,
            text = "Printer Support CNL",
            font = ctk.CTkFont(size= 20, weight= "bold"),
        )
        titulo.grid(row = 0, column = 0, padx = (16, 8), sticky = "w")
        
        self.detect_admin = ctk.CTkLabel(
            sidebar,
            text = "Admin: Ativo" if is_admin() else "Admin: Inativo",
            text_color= "#42f31e" if is_admin() else "#ff9900",
        )
        self.detect_admin.grid(row = 1, column = 0, padx= 12, pady= 4, sticky = "w")
        
        ctk.CTkLabel(sidebar, text= "Impressoras instaladas").grid(row = 2, column = 0, padx = 12, pady= (8, 4),sticky = "w")
        self.lista_impressora = ctk.CTkComboBox(
            sidebar,
            variable = self.selecionar_impressora,
            values = ["Carregando..."],
            height = 38,)
        self.lista_impressora.grid(row = 3, column = 0, padx = 12, pady = 4, sticky = "ew")
        
        ctk.CTkLabel(sidebar, text = "Endereço IP para Teste de PING.").grid(row = 4, column= 0, padx= 10, pady = (12, 4), sticky = "ew")
        ctk.CTkEntry(sidebar, textvariable = self.valor_ip, height = 38).grid(
            row =5, column = 0, padx= 12, pady= 4, sticky = "ew")
    
        
        botoes = [
            ("Instalação Rápida", self._reinstalaçao_rapida),
            ("Correção Automática", self._auto_fix),
            ("Reiniciar Spooler", self._resetar_spooler),
            ("Remover Impressora", self._remover_impressora),
            ("Atualizar lista de Impressoras", self._refresh_printers),
            ("Teste de Conexão", self._run_diagnostic),     
        ]
        for posicao, (texto, chamada) in enumerate(botoes, start=8):
            ctk.CTkButton(
                sidebar, text= texto, command = chamada, height= 40, font= ctk.CTkFont(size= 12, weight= "bold"),).grid(row = posicao, column = 0, padx = 12, pady = 5, sticky = "ew")
            
        content = ctk.CTkFrame(self.root, corner_radius= 12)
        content.grid(row = 0, column = 1, sticky = "nsew", padx = (0,12), pady = 12)
        content.grid_columnconfigure(0, weight= 1)
        content.grid_rowconfigure( 3, weight= 1)
        
        self.status_label = ctk.CTkLabel(
            content,
            textvariable = self.situacao_status,
            font= ctk.CTkFont(size=14, weight= "bold"),)
        self.status_label.grid(row = 0, column = 0, sticky = "w", padx = 14, pady = (14,6))
        
        self.progress = ctk.CTkProgressBar(content, height= 20)
        self.progress.set(0.0)
        self.progress.grid(row = 0, column = 0, padx = 14, pady = 6, sticky = "ew")
        
        self.indicador = ctk.CTkLabel(content, text = "● Idle", text_color="#cccccc")
        self.indicador.grid(row = 2, column = 0, sticky= "w", padx = 14, pady =(0,14))
        
        self.log_box = ctk.CTkTextbox(content, wrap = "word")
        self.log_box.grid(row =3, column= 0, sticky ="nsew", padx =14, pady =(0,14))
        self.log_box.insert("end", "Sistema inicializado.\n")
        self.log_box.configure(state = "disabled")
        
    def run(self):
        self.root.mainloop()
        
    def _append_log(self, text):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {text}\n"
        self.log_queue.put(line)
        self.logger.info(text)
        
    def _kill_fila_log(self):
        while not self.log_queue.empty():
            line = self.log_queue.get_nowait()
            self.log_box.configure(state = "normal")
            self.log_box.insert("end", line)
            self.log_box.see("end")
            self.log_box.configure(state = "disable")
        self.root.after(250, self._kill_fila_log)
        
    def _ocupado(self, busy, status):
        self.situacao_status.set(f"Status: {status}")
        self.indicador.configure(
            text = "● Trabalhando..." if busy else "● Preparar",
            text_color = "#1a85ff" if busy else "#3ad83a" ,
        )
        
        if busy:
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.set(0.0)
            
    def sincronizaçao(self, nome_acao, fn):
        def worker():
            self.root.after(0, lambda: self._ocupado(True,nome_acao))
            try:
                resultado = fn()
                if isinstance(resultado, Resultado_Operacao):
                    self._append_log(resultado.message)
                    if resultado.details:
                        self._append_log(f"Detalhes: {resultado.details}")
                    if resultado.success:
                        self.root.after(0, lambda: messagebox.showinfo("Sucesso", resultado.message))
                    else:
                        self.root.after(0, lambda:messagebox.showerror("Falha", resultado.message))
            except Exception as exc:
                self._append_log(f"Erro inesperado: {exc}")
                self.root.after(0,lambda e = exc: messagebox.showerror("Erro", str(e)))
            finally:
                self.root.after(0,lambda: self._ocupado(False, "Preparar"))
            
        threading.Thread(target= worker, daemon= True).start()
        
    def _selecionar_printer_ou_aviso(self):
        printer = self.selecionar_impressora.get().strip()
        if not printer or printer in ("Carregando...", "Nenhuma impressora encontrada."):
            messagebox.showwarning("Atenção", "Primeiro selecione uma impressora.")
            return None
        return printer

    def _build_fast_reinstall_options(self):
        opcoes = []
        for num in range(1, 11):
            printer_name = f"Impressora {num}"
            ip = f"100.100.190.{100 + num}"
            label = f"{printer_name} -> {ip}"
            opcoes.append((label, printer_name, ip))
        return opcoes
        
    def _require_admin(self):
        if is_admin():
            return True
        messagebox.showwarning(
            "ADMINISTRADOR NECESSÁRIO.",
            "Contate o Suporte de TI"
        )
        return False
    
    def _refresh_printers(self) -> None:
        printers = self.printer_service.printers_instaladas()
        values = [p.name for p in printers] or ["Nenhuma impressora encontrada."]
        self.lista_impressora.configure(values = values)
        self.selecionar_impressora.set(values[0])
        hp_candidatos = [p.name for p in self.printer_service.detectar_HP()]
        self._append_log(f"impressoras detectadas: {len(values)} or HP detectada: {len(hp_candidatos)}")
        
    def _remover_impressora(self):
        if not self._require_admin():
            return
        printer = self._selecionar_printer_ou_aviso()
        if not printer:
            return
        if not messagebox.askyesno("AVISO", f"Remover '{printer}' com drivers e porta? "):
            return
        self.sincronizaçao("Removendo impressora", lambda: self.printer_service.remover_impressora(printer))
        
    def _reinstalar_impressora(self):
        if not self._require_admin():
            return
        printer = self._selecionar_printer_ou_aviso()
        if not printer:
            return
        alvo = self.valor_ip.get().strip()
        if not alvo:
            messagebox.showwarning("Atenção", "Informe o IP ou hostname da Impressora.")
            return
        driver = self.nome_driver.get().strip()
        if not driver:
            messagebox.showwarning("Atenção", "Informe o nome do driver.")
            return
        self.sincronizaçao(
            "Reinstalando impressora",
            lambda: self.printer_service.reinstalar_impressora(printer, alvo, driver),
        )
            
    def _reinstalaçao_rapida(self):
        if not self._require_admin():
            return

        modal = ctk.CTkToplevel(self.root)
        modal.title("Instalacao rápida - Impressora 1 a 10")
        modal.geometry("620x420")
        modal.resizable(False,False)
        modal.transient(self.root)
        modal.grab_set()
        
        frame = ctk.CTkFrame(modal,corner_radius= 10)
        frame.pack(fill = "both", expand = True, padx = 12, pady =12)
        frame.grid_columnconfigure(0, weight= 1)
        
        ctk.CTkLabel(
            frame, text = "Selecione a impressora para instalação automática.",
            font= ctk.CTkFont(size=14, weight= "bold"),
        ).grid(row = 0, column = 0, sticky = "w", padx = 12, pady = (12,8))
        
        opcoes_label = [item[0] for item in self.menu_instalacao]
        selecionar_opcao = ctk.StringVar(value = opcoes_label[0])
        impressora_escolhida = ctk.StringVar(value = self.menu_instalacao[0][1])
        ip_escolhido = ctk.StringVar(value = self.menu_instalacao[0][2])
        driver_escolhido = ctk.StringVar(value= self.nome_driver.get())
        
        def selecao_sincronizada(escolha):
            for label, printer_name, ip in self.menu_instalacao:
                if label == escolha:
                    impressora_escolhida.set(printer_name)
                    ip_escolhido.set(ip)
                    return
                
        combo = ctk.CTkComboBox(
            frame, values= opcoes_label, variable= selecionar_opcao, command=selecao_sincronizada, height= 36,
        )
        combo.grid(row =1, column = 0, sticky = "ew", padx = 12, pady = 6)
        
        ctk.CTkLabel(frame, text= "Nome da Impressora").grid(row =2, column = 0, sticky = "w", padx = 12, pady =(8,2))
        ctk.CTkEntry(frame, textvariable= impressora_escolhida, height= 36).grid( row=3, column =0, sticky = "ew", padx = 12 )
        
        ctk.CTkLabel(frame, text= "IP automático").grid(row =4, column = 0, sticky = "w", padx = 12, pady = (8,2))
        ip_entry = ctk.CTkEntry(frame, textvariable= ip_escolhido, height= 34)
        ip_entry.grid(row =5, column =0, sticky = "ew", padx = 12)
        ip_entry.configure(state = "readonly")
        
        ctk.CTkLabel(frame, text="Driver").grid(row=6, column=0, sticky="w", padx=12, pady=(8, 2))
        ctk.CTkEntry(frame, textvariable=driver_escolhido, height=36).grid(
            row=7, column=0, sticky="ew", padx=12
        )
        
        
        def run_quick_reinstall():
            nome_impressora = impressora_escolhida.get().strip()
            ip = ip_escolhido.get().strip()
            driver = driver_escolhido.get().strip()
            if not nome_impressora or not ip or not driver:
                messagebox.showwarning("atenção", "Preencha nome da impressora e driver.")
                return
            self.selecionar_impressora.set(nome_impressora)
            self.valor_ip.set(ip)
            self.nome_driver.set(driver)
            modal.destroy()
            self.sincronizaçao(
                f"Reinstalção rápida {nome_impressora}",
                lambda: self.printer_service.reinstalar_impressora(nome_impressora, ip, driver),
            )
            
        button_row = ctk.CTkFrame(frame, fg_color="transparent")
        button_row.grid(row = 8, column = 0, sticky ="ew",padx =12, pady =14)
        button_row.grid_columnconfigure(0, weight= 1)
        button_row.grid_columnconfigure(1, weight= 0)
        button_row.grid_columnconfigure(2, weight= 0)
        ctk.CTkButton(
            button_row, text= "OK - Instalar Impressora",
            command= run_quick_reinstall, height= 40, font= ctk.CTkFont(size=14, weight="bold"),
        ).grid(row =0, column = 1, sticky = "e")
        
    def _resetar_spooler(self):
        if not self._require_admin():
            return
        self.sincronizaçao("Reinciando Spooler", self.spooler_service.Resetar_spooler)
        
    def _auto_fix(self):
        if not self._require_admin():
            return
        self.run_auto_fix()
        
    def run_auto_fix(self):
        printer = self._selecionar_printer_ou_aviso()
        if not printer:
            return
        alvo = self.valor_ip.get().strip()
        driver = self.nome_driver.get().strip()
        if not alvo or not driver:
            messagebox.showwarning("Atenção", "forneça o IP/Hostname ou Driver.")
            return
        self.sincronizaçao(
            "Correção automática", lambda: self.auto_fix.one_click_fix(printer, alvo, driver),
        )
        
    def _run_diagnostic(self):
        printer = self._selecionar_printer_ou_aviso()
        if not printer:
            return
        alvo = self.valor_ip.get().strip()
        
        def job():
            report = self.diagnostics_service.run_diagnostic(printer, alvo)
            gerado = self.diagnostics_service.relatorio_tecnico(report)
            msg = (
                f"Diagnóstico completado | ping = {report.ping_ok}, port9100 = {report.porta_9100_ok}, "
                f"Spooler = {report.spooler_rodando}, online = {report.printer_online}"
            )
            detalhes = {"Relatório": gerado.details, "Anotações": report.anotacoes}
            return Resultado_Operacao(gerado.success, msg, detalhes)
        self.sincronizaçao("Executando diagnóstico", job)