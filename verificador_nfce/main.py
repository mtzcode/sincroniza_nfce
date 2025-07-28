import sys
import os
import json
import datetime
import shutil
import threading
import time
import xml.etree.ElementTree as ET
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QLineEdit, QFileDialog,
    QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QSpinBox,
    QSystemTrayIcon, QMenu, QAction, QTabWidget, QComboBox, QDateEdit
)
from PyQt5.QtCore import Qt, QDate, pyqtSignal
from PyQt5.QtGui import QIcon
import concurrent.futures

CONFIG_FILE = 'config.json'
LOG_FILE = 'log.txt'

class VerificadorNFCe(QWidget):
    status_signal = pyqtSignal(str, str, str, str)
    status_geral_signal = pyqtSignal(str, str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Verificador NFC-e')
        self.setGeometry(100, 100, 600, 400)
        self.init_ui()
        self.load_config()
        self.monitorando = False
        self.thread_monitoramento = None
        self.primeira_verificacao = True
        self.tray_icon = None
        self.create_tray_icon()
        # Conectar sinais
        self.status_signal.connect(self._adicionar_status_threadsafe)
        self.status_geral_signal.connect(self._adicionar_status_geral_threadsafe)
        # Inicia o monitoramento automaticamente
        self.toggle_monitoramento()

    def init_ui(self):
        main_layout = QVBoxLayout()
        self.tabs = QTabWidget()
        # Aba principal
        self.tab_principal = QWidget()
        layout = QVBoxLayout()

        # Seleção de pasta de origem
        origem_layout = QHBoxLayout()
        self.origem_edit = QLineEdit()
        self.origem_btn = QPushButton('Selecionar Origem')
        self.origem_btn.clicked.connect(self.selecionar_origem)
        origem_layout.addWidget(QLabel('Pasta de Origem:'))
        origem_layout.addWidget(self.origem_edit)
        origem_layout.addWidget(self.origem_btn)
        layout.addLayout(origem_layout)

        # Seleção de pasta de destino
        destino_layout = QHBoxLayout()
        self.destino_edit = QLineEdit()
        self.destino_btn = QPushButton('Selecionar Destino')
        self.destino_btn.clicked.connect(self.selecionar_destino)
        destino_layout.addWidget(QLabel('Pasta de Destino:'))
        destino_layout.addWidget(self.destino_edit)
        destino_layout.addWidget(self.destino_btn)
        layout.addLayout(destino_layout)

        # Intervalo de verificação
        intervalo_layout = QHBoxLayout()
        self.intervalo_spin = QSpinBox()
        self.intervalo_spin.setMinimum(1)
        self.intervalo_spin.setMaximum(3600)
        self.intervalo_spin.setValue(10)
        intervalo_layout.addWidget(QLabel('Intervalo (segundos):'))
        intervalo_layout.addWidget(self.intervalo_spin)
        layout.addLayout(intervalo_layout)

        # Botão de iniciar/parar
        self.iniciar_btn = QPushButton('Iniciar Monitoramento')
        self.iniciar_btn.clicked.connect(self.toggle_monitoramento)
        layout.addWidget(self.iniciar_btn)

        # Painel de status (tabela)
        self.status_table = QTableWidget(0, 4)
        self.status_table.setHorizontalHeaderLabels(['Arquivo', 'Status', 'Data', 'Hora'])
        layout.addWidget(QLabel('Arquivos Transferidos:'))
        layout.addWidget(self.status_table)

        self.tab_principal.setLayout(layout)
        self.tabs.addTab(self.tab_principal, 'Monitoramento')
        # Aba de histórico
        self.tab_historico = QWidget()
        historico_layout = QVBoxLayout()
        filtro_layout = QHBoxLayout()
        filtro_layout.addWidget(QLabel('Data:'))
        self.filtro_data = QDateEdit()
        self.filtro_data.setCalendarPopup(True)
        self.filtro_data.setDate(QDate.currentDate())
        filtro_layout.addWidget(self.filtro_data)
        filtro_layout.addWidget(QLabel('Status:'))
        self.filtro_status = QComboBox()
        self.filtro_status.addItem('Todos')
        self.filtro_status.addItems(['Copiado', 'Já existe', 'Erro'])
        filtro_layout.addWidget(self.filtro_status)
        self.btn_atualizar_historico = QPushButton('Atualizar Histórico')
        self.btn_atualizar_historico.clicked.connect(self.atualizar_historico)
        filtro_layout.addWidget(self.btn_atualizar_historico)
        historico_layout.addLayout(filtro_layout)
        self.tabela_historico = QTableWidget(0, 4)
        self.tabela_historico.setHorizontalHeaderLabels(['Data', 'Hora', 'Arquivo', 'Status'])
        historico_layout.addWidget(self.tabela_historico)
        self.tab_historico.setLayout(historico_layout)
        self.tabs.addTab(self.tab_historico, 'Histórico')
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)

    def create_tray_icon(self):
        # Tenta usar um ícone customizado, senão usa o padrão do Qt
        icon_path = 'icon.ico'
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
        else:
            icon = self.style().standardIcon(QApplication.style().SP_ComputerIcon)
        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip('Verificador NFC-e')
        # Menu da bandeja
        menu = QMenu()
        show_action = QAction('Mostrar', self)
        quit_action = QAction('Sair', self)
        show_action.triggered.connect(self.showNormal)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(show_action)
        menu.addAction(quit_action)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.showNormal()
            self.activateWindow()

    def selecionar_origem(self):
        pasta = QFileDialog.getExistingDirectory(self, 'Selecionar Pasta de Origem')
        if pasta:
            self.origem_edit.setText(pasta)

    def selecionar_destino(self):
        pasta = QFileDialog.getExistingDirectory(self, 'Selecionar Pasta de Destino')
        if pasta:
            self.destino_edit.setText(pasta)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.origem_edit.setText(config.get('origem', ''))
                self.destino_edit.setText(config.get('destino', ''))
                self.intervalo_spin.setValue(config.get('intervalo', 10))
            except Exception as e:
                print(f'Erro ao carregar configuração: {e}')

    def save_config(self):
        config = {
            'origem': self.origem_edit.text(),
            'destino': self.destino_edit.text(),
            'intervalo': self.intervalo_spin.value()
        }
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f'Erro ao salvar configuração: {e}')

    def closeEvent(self, event):
        # Minimiza para a bandeja ao fechar
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            'Verificador NFC-e',
            'O aplicativo continuará rodando em segundo plano. Clique no ícone para restaurar.',
            QSystemTrayIcon.Information,
            3000
        )
        self.monitorando = False
        if self.thread_monitoramento:
            self.thread_monitoramento.join(timeout=2)
        self.save_config()

    def changeEvent(self, event):
        # Minimiza para a bandeja ao minimizar
        if event.type() == 105:  # QEvent.WindowStateChange
            if self.isMinimized():
                self.hide()
                self.tray_icon.showMessage(
                    'Verificador NFC-e',
                    'O aplicativo foi minimizado para a bandeja.',
                    QSystemTrayIcon.Information,
                    2000
                )
        super().changeEvent(event)

    def criar_estrutura_pastas(self, raiz, ano, pdv, mes):
        caminho = os.path.join(raiz, str(ano), pdv, mes)
        os.makedirs(caminho, exist_ok=True)
        return caminho

    def toggle_monitoramento(self):
        if not self.monitorando:
            self.monitorando = True
            self.iniciar_btn.setText('Parar Monitoramento')
            self.status_table.setRowCount(0)
            self.thread_monitoramento = threading.Thread(target=self.monitorar_loop, daemon=True)
            self.thread_monitoramento.start()
        else:
            self.monitorando = False
            self.iniciar_btn.setText('Iniciar Monitoramento')

    def monitorar_loop(self):
        while self.monitorando:
            total_copiados = self.executar_transferencia_unica(self.primeira_verificacao)
            if total_copiados > 0:
                self.adicionar_status_geral(f"Arquivos atualizados | OK ({total_copiados} copiados)")
            else:
                self.adicionar_status_geral("Nenhum arquivo novo encontrado")
            self.primeira_verificacao = False
            intervalo = self.intervalo_spin.value()
            for _ in range(intervalo):
                if not self.monitorando:
                    break
                time.sleep(1)

    def log_operacao(self, arquivo, status, data, hora, erro=None):
        try:
            # Limitar o tamanho do log a 1MB
            if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 1024 * 1024:
                with open(LOG_FILE, 'w', encoding='utf-8') as f:
                    f.write('')  # Limpa o log
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                linha = f'{data} {hora} | {arquivo} | {status}'
                if erro:
                    linha += f' | {erro}'
                f.write(linha + '\n')
        except Exception as e:
            print(f'Erro ao registrar log: {e}')

    def adicionar_status(self, arquivo, status):
        agora = datetime.datetime.now()
        data_str = agora.strftime('%d/%m/%Y')
        hora_str = agora.strftime('%H:%M:%S')
        self.status_signal.emit(arquivo, status, data_str, hora_str)
        self.log_operacao(arquivo, status, data_str, hora_str)

    def adicionar_status_geral(self, status):
        agora = datetime.datetime.now()
        data_str = agora.strftime('%d/%m/%Y')
        hora_str = agora.strftime('%H:%M:%S')
        self.status_geral_signal.emit(status, data_str, hora_str)

    def validar_xml(self, caminho_arquivo):
        try:
            ET.parse(caminho_arquivo)
            return True
        except Exception:
            return False

    def _adicionar_status_threadsafe(self, arquivo, status, data_str, hora_str):
        row = self.status_table.rowCount()
        self.status_table.insertRow(row)
        self.status_table.setItem(row, 0, QTableWidgetItem(arquivo))
        self.status_table.setItem(row, 1, QTableWidgetItem(status))
        self.status_table.setItem(row, 2, QTableWidgetItem(data_str))
        self.status_table.setItem(row, 3, QTableWidgetItem(hora_str))

    def _adicionar_status_geral_threadsafe(self, status, data_str, hora_str):
        if self.status_table.rowCount() > 0:
            last_row = self.status_table.rowCount() - 1
            if self.status_table.item(last_row, 0) and self.status_table.item(last_row, 0).text() == '---':
                self.status_table.removeRow(last_row)
        row = self.status_table.rowCount()
        self.status_table.insertRow(row)
        self.status_table.setItem(row, 0, QTableWidgetItem('---'))
        self.status_table.setItem(row, 1, QTableWidgetItem(status))
        self.status_table.setItem(row, 2, QTableWidgetItem(data_str))
        self.status_table.setItem(row, 3, QTableWidgetItem(hora_str))

    def processar_arquivo(self, arquivo, caminho_arquivo, ano, mes, pdv, pasta_destino, destino_final, mostrar_ja_existe, data_str, hora_str):
        try:
            if os.path.exists(destino_final):
                if mostrar_ja_existe:
                    self.status_signal.emit(arquivo, 'Já existe', data_str, hora_str)
                self.log_operacao(arquivo, 'Já existe', data_str, hora_str)
                return 0
            if not self.validar_xml(caminho_arquivo):
                self.status_signal.emit(arquivo, 'XML Inválido', data_str, hora_str)
                self.log_operacao(arquivo, 'XML Inválido', data_str, hora_str)
                return 0
            shutil.copy2(caminho_arquivo, destino_final)
            self.status_signal.emit(arquivo, 'Copiado', data_str, hora_str)
            self.log_operacao(arquivo, 'Copiado', data_str, hora_str)
            return 1
        except Exception as e:
            self.status_signal.emit(arquivo, f'Erro: {e}', data_str, hora_str)
            self.log_operacao(arquivo, 'Erro', data_str, hora_str, str(e))
            return 0

    def executar_transferencia_unica(self, mostrar_ja_existe=False):
        origem = self.origem_edit.text()
        destino_base = self.destino_edit.text()
        if not origem or not destino_base:
            return 0
        total_copiados = 0
        tarefas = []
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                for subpasta in os.listdir(origem):
                    caminho_mes = os.path.join(origem, subpasta)
                    if os.path.isdir(caminho_mes) and subpasta.lower().startswith('mes'):
                        arquivos_xml = [f for f in os.listdir(caminho_mes) if f.lower().endswith('.xml')]
                        if not arquivos_xml:
                            continue
                        for arquivo in arquivos_xml:
                            caminho_arquivo = os.path.join(caminho_mes, arquivo)
                            ano = self.extrair_ano_da_origem(origem)
                            mes = subpasta.upper()
                            pdv = f"PDV-{arquivo[22:25]}"
                            pasta_destino = self.criar_estrutura_pastas(os.path.join(destino_base, 'NFCE'), ano, pdv, mes)
                            destino_final = os.path.join(pasta_destino, arquivo)
                            agora = datetime.datetime.now()
                            data_str = agora.strftime('%d/%m/%Y')
                            hora_str = agora.strftime('%H:%M:%S')
                            tarefas.append(executor.submit(
                                self.processar_arquivo,
                                arquivo, caminho_arquivo, ano, mes, pdv, pasta_destino, destino_final, mostrar_ja_existe, data_str, hora_str
                            ))
                for future in concurrent.futures.as_completed(tarefas):
                    try:
                        total_copiados += future.result()
                    except Exception as e:
                        print(f'Erro em thread de cópia: {e}')
        except Exception as e:
            print(f'Erro no ciclo de monitoramento: {e}')
        return total_copiados

    def extrair_ano_da_origem(self, origem):
        partes = origem.split(os.sep)
        for parte in partes:
            if parte.lower().startswith('ano'):
                try:
                    return int(parte.split()[-1])
                except:
                    pass
        return datetime.datetime.now().year

    def atualizar_historico(self):
        self.tabela_historico.setRowCount(0)
        data_filtro = self.filtro_data.date().toString('dd/MM/yyyy')
        status_filtro = self.filtro_status.currentText()
        if not os.path.exists(LOG_FILE):
            return
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            for linha in f:
                partes = linha.strip().split(' | ')
                if len(partes) < 3:
                    continue
                data_h, hora_h = partes[0].split(' ')
                arquivo_h = partes[1]
                status_h = partes[2]
                if status_filtro != 'Todos' and status_h != status_filtro:
                    continue
                if data_h != data_filtro:
                    continue
                row = self.tabela_historico.rowCount()
                self.tabela_historico.insertRow(row)
                self.tabela_historico.setItem(row, 0, QTableWidgetItem(data_h))
                self.tabela_historico.setItem(row, 1, QTableWidgetItem(hora_h))
                self.tabela_historico.setItem(row, 2, QTableWidgetItem(arquivo_h))
                self.tabela_historico.setItem(row, 3, QTableWidgetItem(status_h))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VerificadorNFCe()
    window.show()
    sys.exit(app.exec_()) 