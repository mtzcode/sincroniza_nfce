import sys
import os
import json
import datetime
import shutil
import threading
import time
import xml.etree.ElementTree as ET
import re
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QLineEdit, QFileDialog,
    QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QSpinBox,
    QSystemTrayIcon, QMenu, QAction, QTabWidget, QComboBox, QDateEdit, QMessageBox
)
from PyQt5.QtCore import Qt, QDate, pyqtSignal, QTimer, QThread, QObject
from PyQt5.QtGui import QIcon
import concurrent.futures
import requests
import subprocess
import tempfile

CONFIG_FILE = 'config.json'
LOG_FILE = 'log.txt'

VERSION = "1.0.3"
GITHUB_REPO = "mtzcode/sincroniza_nfce"
GITHUB_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

class MonitoramentoWorker(QObject):
    """Worker para executar o monitoramento em thread separada"""
    status_signal = pyqtSignal(str, str, str, str)
    status_geral_signal = pyqtSignal(str, str, str)
    finished = pyqtSignal()
    
    def __init__(self, verificador):
        super().__init__()
        self.verificador = verificador
        self.monitorando = False
        self.primeira_verificacao = True
    
    def iniciar_monitoramento(self):
        self.monitorando = True
        self.loop_monitoramento()
    
    def parar_monitoramento(self):
        self.monitorando = False
    
    def loop_monitoramento(self):
        while self.monitorando:
            try:
                total_copiados = self.verificador.executar_transferencia_unica(self.primeira_verificacao)
                
                if total_copiados > 0:
                    self.status_geral_signal.emit(f"Arquivos atualizados | OK ({total_copiados} copiados)", "", "")
                else:
                    self.status_geral_signal.emit("Nenhum arquivo novo encontrado", "", "")
                
                self.primeira_verificacao = False
                
                # Aguardar intervalo (verificando se deve parar a cada segundo)
                intervalo = self.verificador.intervalo_spin.value()
                for _ in range(intervalo):
                    if not self.monitorando:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                print(f"Erro no loop de monitoramento: {e}")
                # Em caso de erro, aguarda um pouco antes de tentar novamente
                time.sleep(5)
        
        self.finished.emit()

class VerificadorNFCe(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Verificador NFC-e')
        self.setGeometry(100, 100, 600, 400)
        
        # Variáveis de controle
        self.monitorando = False
        self.worker = None
        self.worker_thread = None
        self.tray_icon = None
        self._monitoramento_iniciado = False
        
        # Inicializar interface
        self.init_ui()
        
        # Flag para controlar se deve mostrar a janela
        self.deve_mostrar_janela = False
        
        # Flag para controlar se o usuário abriu manualmente
        self.usuario_abriu_manualmente = False
        
        # Carregar configuração (isso pode alterar a flag)
        self.load_config()
        
        self.create_tray_icon()
        
        # Timer para verificação periódica (alternativa mais estável)
        self.timer_verificacao = QTimer()
        self.timer_verificacao.timeout.connect(self.verificacao_timer)
        self.primeira_verificacao = True
        
        # A janela será mostrada apenas se necessário (configuração pendente)
        # Não mostrar automaticamente no início se tudo estiver configurado
        if not self.deve_mostrar_janela:
            # Esconder a janela se tudo estiver configurado
            self.hide()
        else:
            # Mostrar a janela se houver configuração pendente
            self.usuario_abriu_manualmente = False  # Resetar flag
            QTimer.singleShot(500, self.showNormal)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._monitoramento_iniciado:
            # Aguardar um pouco antes de iniciar automaticamente
            QTimer.singleShot(1000, self.iniciar_automaticamente)
            self._monitoramento_iniciado = True
        else:
            # Se não for a primeira vez, verificar se deve minimizar
            # IMPORTANTE: NUNCA minimizar se o usuário abriu manualmente
            if self.usuario_abriu_manualmente:
                return  # Sair sem fazer nada se o usuário abriu manualmente
                
            if self.monitorando and not self.deve_mostrar_janela:
                # Aguardar um pouco antes de minimizar para dar tempo do usuário ver
                QTimer.singleShot(1000, self.minimizar_para_bandeja)
            elif not self.monitorando and self.deve_mostrar_janela:
                # Se não estiver monitorando e deve mostrar, manter visível
                pass

    def iniciar_automaticamente(self):
        """Inicia o monitoramento automaticamente e decide se deve mostrar ou minimizar"""
        # Verificar se as pastas estão configuradas
        if not self.origem_edit.text() or not self.destino_edit.text():
            # Pastas não configuradas - mostrar na tela para o usuário configurar
            self.adicionar_status_geral("Configure as pastas de origem e destino")
            self.deve_mostrar_janela = True
            self.usuario_abriu_manualmente = False  # Resetar flag
            # Mostrar a janela para o usuário configurar
            self.showNormal()
            self.activateWindow()
            return
        
        # Pastas configuradas - iniciar monitoramento
        self.monitorando = True
        self.iniciar_btn.setText('Parar Monitoramento')
        self.status_table.setRowCount(0)
        self.primeira_verificacao = True
        
        # Usar timer ao invés de thread para maior estabilidade
        intervalo_ms = self.intervalo_spin.value() * 1000
        self.timer_verificacao.start(intervalo_ms)
        
        self.adicionar_status_geral("Monitoramento iniciado automaticamente")
        
        # Se tudo estiver funcionando, minimizar para a bandeja
        self.deve_mostrar_janela = False
        self.usuario_abriu_manualmente = False  # Resetar flag
        # Aguardar um pouco para mostrar o status e depois minimizar
        QTimer.singleShot(2000, self.minimizar_para_bandeja)

    def minimizar_para_bandeja(self):
        """Minimiza o aplicativo para a bandeja do sistema"""
        # NUNCA minimizar se o usuário abriu manualmente
        if self.usuario_abriu_manualmente:
            return
            
        if (self.monitorando and self.origem_edit.text() and self.destino_edit.text() 
            and not self.deve_mostrar_janela):
            self.hide()
            if self.tray_icon:
                self.tray_icon.showMessage(
                    'Verificador NFC-e',
                    'Monitoramento ativo. O aplicativo está rodando na bandeja do sistema.',
                    QSystemTrayIcon.Information,
                    3000
                )

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
        self.intervalo_spin.valueChanged.connect(self.intervalo_alterado)
        intervalo_layout.addWidget(QLabel('Intervalo (segundos):'))
        intervalo_layout.addWidget(self.intervalo_spin)
        layout.addLayout(intervalo_layout)

        # Botões de controle
        botoes_layout = QHBoxLayout()
        self.iniciar_btn = QPushButton('Iniciar Monitoramento')
        self.iniciar_btn.clicked.connect(self.toggle_monitoramento)
        self.atualizar_btn = QPushButton('Verificar Atualizações')
        self.atualizar_btn.clicked.connect(self.verificar_atualizacao)
        self.verificar_agora_btn = QPushButton('Verificar Agora')
        self.verificar_agora_btn.clicked.connect(self.verificar_agora)
        botoes_layout.addWidget(self.iniciar_btn)
        botoes_layout.addWidget(self.verificar_agora_btn)
        botoes_layout.addWidget(self.atualizar_btn)
        layout.addLayout(botoes_layout)

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
        self.filtro_status.addItems(['Copiado', 'Já existe', 'Erro', 'XML Inválido'])
        filtro_layout.addWidget(self.filtro_status)
        
        self.btn_atualizar_historico = QPushButton('Atualizar Histórico')
        self.btn_atualizar_historico.clicked.connect(self.atualizar_historico)
        filtro_layout.addWidget(self.btn_atualizar_historico)
        
        self.btn_limpar_filtros = QPushButton('Limpar Filtros')
        self.btn_limpar_filtros.clicked.connect(self.limpar_filtros_historico)
        filtro_layout.addWidget(self.btn_limpar_filtros)
        historico_layout.addLayout(filtro_layout)
        
        self.tabela_historico = QTableWidget(0, 4)
        self.tabela_historico.setHorizontalHeaderLabels(['Data', 'Hora', 'Arquivo', 'Status'])
        historico_layout.addWidget(self.tabela_historico)
        
        self.tab_historico.setLayout(historico_layout)
        self.tabs.addTab(self.tab_historico, 'Histórico')
        
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)

    def intervalo_alterado(self):
        """Atualiza o timer quando o intervalo é alterado"""
        # Resetar flag quando o usuário interagir com a interface
        self.usuario_abriu_manualmente = False
        if self.monitorando:
            self.timer_verificacao.setInterval(self.intervalo_spin.value() * 1000)

    def verificar_agora(self):
        """Executa uma verificação manual imediata"""
        # Resetar flag quando o usuário interagir com a interface
        self.usuario_abriu_manualmente = False
        self.verificar_agora_btn.setEnabled(False)
        self.verificar_agora_btn.setText('Verificando...')
        
        try:
            total_copiados = self.executar_transferencia_unica(True)
            if total_copiados > 0:
                self.adicionar_status_geral(f"Verificação manual | OK ({total_copiados} copiados)")
            else:
                self.adicionar_status_geral("Verificação manual | Nenhum arquivo novo")
        except Exception as e:
            self.adicionar_status_geral(f"Verificação manual | Erro: {e}")
        finally:
            self.verificar_agora_btn.setEnabled(True)
            self.verificar_agora_btn.setText('Verificar Agora')
            
            # Minimizar para a bandeja após verificação manual (se estiver monitorando)
            if self.monitorando:
                self.deve_mostrar_janela = False
                self.usuario_abriu_manualmente = False  # Resetar flag
                # Aguardar um pouco para mostrar o status e depois minimizar
                QTimer.singleShot(2000, self.minimizar_para_bandeja)

    def verificacao_timer(self):
        """Executa verificação pelo timer"""
        try:
            total_copiados = self.executar_transferencia_unica(self.primeira_verificacao)
            if total_copiados > 0:
                self.adicionar_status_geral(f"Arquivos atualizados | OK ({total_copiados} copiados)")
            else:
                self.adicionar_status_geral("Nenhum arquivo novo encontrado")
            self.primeira_verificacao = False
        except Exception as e:
            self.adicionar_status_geral(f"Erro na verificação: {e}")
            print(f"Erro na verificação timer: {e}")
            # Mostrar na tela quando houver erro
            self.deve_mostrar_janela = True
            self.usuario_abriu_manualmente = False  # Resetar flag
            self.showNormal()
            self.activateWindow()

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
        quit_action.triggered.connect(self.fechar_aplicacao)
        menu.addAction(show_action)
        menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            # Marcar que o usuário abriu manualmente ANTES de mostrar a janela
            self.usuario_abriu_manualmente = True
            # Aguardar um pouco para garantir que a flag seja processada
            QTimer.singleShot(100, self.mostrar_janela_usuario)

    def mostrar_janela_usuario(self):
        """Mostra a janela quando o usuário clica no ícone da bandeja"""
        self.showNormal()
        self.activateWindow()
        # Garantir que a janela permaneça visível
        self.raise_()
        self.setFocus()

    def selecionar_origem(self):
        # Resetar flag quando o usuário interagir com a interface
        self.usuario_abriu_manualmente = False
        pasta = QFileDialog.getExistingDirectory(self, 'Selecionar Pasta de Origem')
        if pasta:
            self.origem_edit.setText(pasta)
            self.save_config()

    def selecionar_destino(self):
        # Resetar flag quando o usuário interagir com a interface
        self.usuario_abriu_manualmente = False
        pasta = QFileDialog.getExistingDirectory(self, 'Selecionar Pasta de Destino')
        if pasta:
            self.destino_edit.setText(pasta)
            self.save_config()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.origem_edit.setText(config.get('origem', ''))
                self.destino_edit.setText(config.get('destino', ''))
                self.intervalo_spin.setValue(config.get('intervalo', 10))
                
                # Verificar se as pastas estão configuradas
                if not config.get('origem') or not config.get('destino'):
                    self.deve_mostrar_janela = True
                    self.usuario_abriu_manualmente = False  # Resetar flag
                else:
                    self.deve_mostrar_janela = False
            except Exception as e:
                print(f'Erro ao carregar configuração: {e}')
                self.deve_mostrar_janela = True
                self.usuario_abriu_manualmente = False  # Resetar flag
        else:
            # Arquivo de configuração não existe - deve mostrar para configurar
            self.deve_mostrar_janela = True
            self.usuario_abriu_manualmente = False  # Resetar flag

    def save_config(self):
        # Resetar flag quando o usuário salvar configuração
        self.usuario_abriu_manualmente = False
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

    def toggle_monitoramento(self):
        # Resetar flag quando o usuário interagir com a interface
        self.usuario_abriu_manualmente = False
        if not self.monitorando:
            # Verificar se as pastas foram configuradas
            if not self.origem_edit.text() or not self.destino_edit.text():
                self.mostrar_mensagem('Erro', 'Por favor, configure as pastas de origem e destino.')
                return
            
            self.monitorando = True
            self.iniciar_btn.setText('Parar Monitoramento')
            self.status_table.setRowCount(0)
            self.primeira_verificacao = True
            
            # Usar timer ao invés de thread para maior estabilidade
            intervalo_ms = self.intervalo_spin.value() * 1000
            self.timer_verificacao.start(intervalo_ms)
            
            self.adicionar_status_geral("Monitoramento iniciado")
            
            # Minimizar para a bandeja após iniciar
            self.deve_mostrar_janela = False
            self.usuario_abriu_manualmente = False  # Resetar flag
            # Aguardar um pouco para mostrar o status e depois minimizar
            QTimer.singleShot(2000, self.minimizar_para_bandeja)
        else:
            self.monitorando = False
            self.iniciar_btn.setText('Iniciar Monitoramento')
            self.timer_verificacao.stop()
            self.adicionar_status_geral("Monitoramento parado")
            
            # Mostrar na tela quando parar o monitoramento
            self.deve_mostrar_janela = True
            self.usuario_abriu_manualmente = False  # Resetar flag
            self.showNormal()
            self.activateWindow()

    def fechar_aplicacao(self):
        """Fecha completamente a aplicação"""
        self.monitorando = False
        if self.timer_verificacao.isActive():
            self.timer_verificacao.stop()
        self.save_config()
        QApplication.instance().quit()

    def closeEvent(self, event):
        # Minimiza para a bandeja ao fechar
        event.ignore()
        # Resetar flag quando o usuário fechar
        self.usuario_abriu_manualmente = False
        self.hide()
        if self.tray_icon:
            self.tray_icon.showMessage(
                'Verificador NFC-e',
                'O aplicativo continuará rodando em segundo plano. Clique no ícone para restaurar.',
                QSystemTrayIcon.Information,
                3000
            )

    def changeEvent(self, event):
        # Minimiza para a bandeja ao minimizar
        if event.type() == 105:  # QEvent.WindowStateChange
            if self.isMinimized():
                # Resetar flag quando o usuário minimizar
                self.usuario_abriu_manualmente = False
                self.hide()
                if self.tray_icon:
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

    def log_operacao(self, arquivo, status, data, hora, erro=None):
        try:
            # Limitar o tamanho do log a 1MB
            if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 1024 * 1024:
                with open(LOG_FILE, 'w', encoding='utf-8') as f:
                    f.write('')  # Limpa o log
            
            # Registrar TODOS os status para o histórico
            # Removido o filtro que impedia alguns status de serem registrados
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
        
        # Adicionar diretamente na thread principal (já que chamamos do timer)
        row = self.status_table.rowCount()
        self.status_table.insertRow(row)
        self.status_table.setItem(row, 0, QTableWidgetItem(arquivo))
        self.status_table.setItem(row, 1, QTableWidgetItem(status))
        self.status_table.setItem(row, 2, QTableWidgetItem(data_str))
        self.status_table.setItem(row, 3, QTableWidgetItem(hora_str))
        
        self.log_operacao(arquivo, status, data_str, hora_str)

    def adicionar_status_geral(self, status):
        agora = datetime.datetime.now()
        data_str = agora.strftime('%d/%m/%Y')
        hora_str = agora.strftime('%H:%M:%S')
        
        # Remover última linha de status geral se existir
        if self.status_table.rowCount() > 0:
            last_row = self.status_table.rowCount() - 1
            if (self.status_table.item(last_row, 0) and 
                self.status_table.item(last_row, 0).text() == 'Status Geral'):
                self.status_table.removeRow(last_row)
        
        row = self.status_table.rowCount()
        self.status_table.insertRow(row)
        self.status_table.setItem(row, 0, QTableWidgetItem('Status Geral'))
        self.status_table.setItem(row, 1, QTableWidgetItem(status))
        self.status_table.setItem(row, 2, QTableWidgetItem(data_str))
        self.status_table.setItem(row, 3, QTableWidgetItem(hora_str))

    def validar_xml(self, caminho_arquivo):
        try:
            ET.parse(caminho_arquivo)
            return True
        except Exception:
            return False

    def processar_arquivo(self, arquivo, caminho_arquivo, ano, mes, pdv, pasta_destino, destino_final, mostrar_ja_existe):
        try:
            if os.path.exists(destino_final):
                if mostrar_ja_existe:
                    self.adicionar_status(arquivo, 'Já existe')
                return 0
            
            if not self.validar_xml(caminho_arquivo):
                self.adicionar_status(arquivo, 'XML Inválido')
                return 0
            
            shutil.copy2(caminho_arquivo, destino_final)
            self.adicionar_status(arquivo, 'Copiado')
            return 1
            
        except Exception as e:
            self.adicionar_status(arquivo, f'Erro: {e}')
            return 0

    def executar_transferencia_unica(self, mostrar_ja_existe=False):
        origem = self.origem_edit.text()
        destino_base = self.destino_edit.text()
        
        if not origem or not destino_base:
            # Mostrar na tela quando não houver configuração
            self.deve_mostrar_janela = True
            self.usuario_abriu_manualmente = False  # Resetar flag
            self.showNormal()
            self.activateWindow()
            return 0
        
        if not os.path.exists(origem):
            self.adicionar_status_geral("Pasta de origem não encontrada")
            # Mostrar na tela quando houver problema com pastas
            self.deve_mostrar_janela = True
            self.usuario_abriu_manualmente = False  # Resetar flag
            self.showNormal()
            self.activateWindow()
            return 0
        
        total_copiados = 0
        
        try:
            for subpasta in os.listdir(origem):
                caminho_mes = os.path.join(origem, subpasta)
                if os.path.isdir(caminho_mes) and subpasta.lower().startswith('mes'):
                    try:
                        arquivos_xml = [f for f in os.listdir(caminho_mes) if f.lower().endswith('.xml')]
                        if not arquivos_xml:
                            continue
                        
                        for arquivo in arquivos_xml:
                            if not self.monitorando:  # Verificar se ainda deve continuar
                                break
                                
                            caminho_arquivo = os.path.join(caminho_mes, arquivo)
                            
                            # Extrair informações do arquivo
                            ano = self.extrair_ano_da_origem(origem)
                            mes = subpasta.upper()
                            
                            # Extrair PDV baseado no tipo de arquivo
                            pdv = self.extrair_pdv_do_arquivo(arquivo)
                            
                            pasta_destino = self.criar_estrutura_pastas(
                                os.path.join(destino_base, 'NFCE'), ano, pdv, mes
                            )
                            destino_final = os.path.join(pasta_destino, arquivo)
                            
                            resultado = self.processar_arquivo(
                                arquivo, caminho_arquivo, ano, mes, pdv, 
                                pasta_destino, destino_final, mostrar_ja_existe
                            )
                            total_copiados += resultado
                            
                    except Exception as e:
                        print(f'Erro ao processar subpasta {subpasta}: {e}')
                        continue
                        
        except Exception as e:
            print(f'Erro no ciclo de monitoramento: {e}')
            self.adicionar_status_geral(f"Erro no monitoramento: {e}")
        
        return total_copiados

    def extrair_pdv_do_arquivo(self, nome_arquivo):
        """
        Extrai o número do PDV baseado no tipo de arquivo.
        Detecta automaticamente se é NFCe ou InutNFCe e extrai das posições corretas.
        """
        try:
            # Remover extensão .xml se existir
            nome_sem_ext = nome_arquivo.replace('.xml', '')
            
            # Verificar se é arquivo de inutilização (InutNFCe)
            if 'InutNFCe' in nome_arquivo:
                # Para InutNFCe: posições 21-23 (ex: 35252434286900018265031000001542000001542-InutNFCe.xml)
                if len(nome_sem_ext) >= 23:
                    pdv_numero = nome_sem_ext[20:23]  # Posições 21-23 (0-indexed)
                    print(f"DEBUG - InutNFCe detectado: {nome_arquivo} -> PDV: {pdv_numero}")
                    return f"PDV-{pdv_numero}"
                else:
                    print(f"DEBUG - InutNFCe muito curto: {nome_arquivo}")
                    return "PDV-000"
            
            # Para NFCe normal: posições 23-25 (ex: 35250802775652000123650310000000901564004651-NFCe.xml)
            elif 'NFCe' in nome_arquivo:
                if len(nome_sem_ext) >= 25:
                    pdv_numero = nome_sem_ext[22:25]  # Posições 23-25 (0-indexed)
                    print(f"DEBUG - NFCe detectado: {nome_arquivo} -> PDV: {pdv_numero}")
                    return f"PDV-{pdv_numero}"
                else:
                    print(f"DEBUG - NFCe muito curto: {nome_arquivo}")
                    return "PDV-000"
            
            # Para outros tipos de arquivo, tentar detectar automaticamente
            else:
                # Tentar encontrar padrão de 3 dígitos que pode ser o PDV
                # Procurar por sequência de 3 dígitos após um padrão específico
                # Padrão: procurar por 3 dígitos após uma sequência de números
                match = re.search(r'\d{3}(?=\d{11,})', nome_sem_ext)
                if match:
                    pdv_numero = match.group()
                    print(f"DEBUG - Padrão genérico detectado: {nome_arquivo} -> PDV: {pdv_numero}")
                    return f"PDV-{pdv_numero}"
                else:
                    print(f"DEBUG - Nenhum padrão encontrado: {nome_arquivo}")
                    return "PDV-000"
                    
        except Exception as e:
            print(f"Erro ao extrair PDV do arquivo {nome_arquivo}: {e}")
            return "PDV-000"

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
        # Resetar flag quando o usuário interagir com a interface
        self.usuario_abriu_manualmente = False
        self.tabela_historico.setRowCount(0)
        data_filtro = self.filtro_data.date().toString('dd/MM/yyyy')
        status_filtro = self.filtro_status.currentText()
        
        if not os.path.exists(LOG_FILE):
            return
        
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                for linha in f:
                    partes = linha.strip().split(' | ')
                    if len(partes) < 3:
                        continue
                    
                    data_h, hora_h = partes[0].split(' ')
                    arquivo_h = partes[1]
                    status_h = partes[2]
                    
                    # Lógica de filtros melhorada
                    deve_mostrar = True
                    
                    # Filtro de status
                    if status_filtro != 'Todos' and status_h != status_filtro:
                        deve_mostrar = False
                    
                    # Filtro de data - só aplicar se não for "Todos" no status
                    if deve_mostrar and status_filtro == 'Todos':
                        # Se status é "Todos", não filtrar por data
                        pass
                    elif deve_mostrar and data_h != data_filtro:
                        # Se status não é "Todos", aplicar filtro de data
                        deve_mostrar = False
                    
                    # Adicionar linha se deve mostrar
                    if deve_mostrar:
                        row = self.tabela_historico.rowCount()
                        self.tabela_historico.insertRow(row)
                        self.tabela_historico.setItem(row, 0, QTableWidgetItem(data_h))
                        self.tabela_historico.setItem(row, 1, QTableWidgetItem(hora_h))
                        self.tabela_historico.setItem(row, 2, QTableWidgetItem(arquivo_h))
                        self.tabela_historico.setItem(row, 3, QTableWidgetItem(status_h))
                
                # Mostrar mensagem se não houver resultados
                if self.tabela_historico.rowCount() == 0:
                    row = self.tabela_historico.rowCount()
                    self.tabela_historico.insertRow(row)
                    self.tabela_historico.setItem(row, 0, QTableWidgetItem("Nenhum resultado"))
                    self.tabela_historico.setItem(row, 1, QTableWidgetItem(""))
                    self.tabela_historico.setItem(row, 2, QTableWidgetItem(""))
                    self.tabela_historico.setItem(row, 3, QTableWidgetItem(""))
                        
        except Exception as e:
            print(f'Erro ao atualizar histórico: {e}')
            # Mostrar erro na interface
            self.adicionar_status_geral(f"Erro ao carregar histórico: {e}")

    def limpar_filtros_historico(self):
        """Limpa os filtros e atualiza o histórico"""
        # Resetar flag quando o usuário interagir com a interface
        self.usuario_abriu_manualmente = False
        
        # Limpar filtros
        self.filtro_data.setDate(QDate.currentDate())
        self.filtro_status.setCurrentText('Todos')
        
        # Atualizar histórico
        self.atualizar_historico()

    def verificar_atualizacao(self):
        # Resetar flag quando o usuário interagir com a interface
        self.usuario_abriu_manualmente = False
        try:
            self.atualizar_btn.setEnabled(False)
            self.atualizar_btn.setText('Verificando...')
            
            # Headers para acessar repositório
            headers = {
                'User-Agent': 'VerificadorNFCe/1.0.0',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            # Verificar versão mais recente no GitHub
            response = requests.get(GITHUB_RELEASE_URL, headers=headers, timeout=10)
            if response.status_code == 200:
                release_data = response.json()
                latest_version = release_data['tag_name'].lstrip('v')
                
                if latest_version > VERSION:
                    # Há atualização disponível
                    download_url = None
                    for asset in release_data['assets']:
                        if asset['name'].endswith('.exe'):
                            download_url = asset['browser_download_url']
                            break
                    
                    if download_url:
                        self.baixar_e_instalar_atualizacao(download_url)
                    else:
                        self.mostrar_mensagem('Erro', 'Arquivo executável não encontrado na versão mais recente.')
                else:
                    self.mostrar_mensagem('Atualização', 'Você já está usando a versão mais recente.')
            else:
                self.mostrar_mensagem('Erro', f'Não foi possível verificar atualizações. Status: {response.status_code}')
        except Exception as e:
            self.mostrar_mensagem('Erro', f'Erro ao verificar atualização: {str(e)}')
        finally:
            self.atualizar_btn.setEnabled(True)
            self.atualizar_btn.setText('Verificar Atualizações')

    def baixar_e_instalar_atualizacao(self, download_url):
        try:
            # Baixar nova versão
            response = requests.get(download_url, stream=True)
            if response.status_code == 200:
                # Salvar em arquivo temporário
                with tempfile.NamedTemporaryFile(delete=False, suffix='.exe') as temp_file:
                    for chunk in response.iter_content(chunk_size=8192):
                        temp_file.write(chunk)
                    temp_path = temp_file.name
                
                # Criar script de atualização
                atualizador_script = f"""
import os
import time
import subprocess
import sys

# Aguardar aplicativo atual fechar
time.sleep(2)

# Substituir executável
try:
    os.remove(r"{sys.executable}")
    os.rename(r"{temp_path}", r"{sys.executable}")
    
    # Reiniciar aplicativo
    subprocess.Popen([r"{sys.executable}"])
except Exception as e:
    print(f"Erro na atualização: {{e}}")
"""
                
                # Salvar e executar script de atualização
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as script_file:
                    script_file.write(atualizador_script)
                    script_path = script_file.name
                
                # Executar script de atualização
                subprocess.Popen([sys.executable, script_path])
                
                # Fechar aplicativo atual
                self.fechar_aplicacao()
            else:
                self.mostrar_mensagem('Erro', 'Falha ao baixar atualização.')
        except Exception as e:
            self.mostrar_mensagem('Erro', f'Erro ao instalar atualização: {str(e)}')

    def mostrar_mensagem(self, titulo, mensagem):
        msg = QMessageBox()
        msg.setWindowTitle(titulo)
        msg.setText(mensagem)
        msg.exec_()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Configurar aplicação para não fechar quando a janela é fechada
    app.setQuitOnLastWindowClosed(False)
    
    window = VerificadorNFCe()
    # Não mostrar automaticamente - será controlado pela lógica interna
    # window.show()
    
    sys.exit(app.exec_())
