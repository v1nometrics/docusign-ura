#!/usr/bin/env python3
"""
Sistema de Monitoramento Contnuo de Contratos no S3

Este script monitora continuamente o bucket S3 em busca de novos contratos
e os processa automaticamente assim que so detectados.

Caractersticas:
- Monitoramento inteligente com polling adaptativo
- Deteco automtica de novos contratos
- Processamento imediato com gerao de links
- Sistema de cache para evitar reprocessamento
- Tratamento robusto de erros e retries
- Logs detalhados para auditoria
- Modo daemon/service para execuo contnua
"""

import time
import json
import logging
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set
import threading

from app.aws_s3_helper import S3Helper
from app.jwt_config import AWS_CONFIG

# Configuraes do sistema
MONITOR_CONFIG = {
    "poll_interval_fast": 5,     # segundos (quando h atividade recente)
    "poll_interval_normal": 30,  # segundos (atividade normal)
    "poll_interval_slow": 120,   # segundos (sem atividade recente)
    "max_retries": 3,           # tentativas de processamento
    "retry_delay": 5,           # segundos entre retries
    "cache_file": "contrato_cache.json",
    "log_file": "contrato_monitor.log",
    "processed_dir": "processed_contracts"
}

class ContratoMonitor:
    """
    Monitor de contratos com processamento automtico
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.s3_helper = None
        self.processed_contracts: Set[str] = set()
        self.last_activity = datetime.now()
        self.running = True
        self.stats = {
            "contracts_processed": 0,
            "errors": 0,
            "start_time": datetime.now(),
            "last_check": None
        }

        # Setup signal handlers para graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Inicializar sistema
        self._setup_logging()
        self._load_cache()
        self._create_directories()
        self._init_s3_client()

    def _setup_logging(self):
        """Configura sistema de logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(MONITOR_CONFIG["log_file"]),
                logging.StreamHandler(sys.stdout)
            ],
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("Sistema de Monitoramento de Contratos iniciado")

    def _create_directories(self):
        """Cria diretrios necessrios"""
        Path(MONITOR_CONFIG["processed_dir"]).mkdir(exist_ok=True)
        self.logger.debug(f"Diretorio criado: {MONITOR_CONFIG['processed_dir']}")

    def _init_s3_client(self):
        """Inicializa cliente S3"""
        try:
            self.s3_helper = S3Helper(
                access_key=AWS_CONFIG["access_key_id"],
                secret_key=AWS_CONFIG["secret_access_key"],
                region=AWS_CONFIG["region"],
                bucket_name=AWS_CONFIG["bucket_name"]
            )
            self.logger.info(" Cliente S3 inicializado com sucesso")
        except Exception as e:
            self.logger.error(f" Falha ao inicializar cliente S3: {str(e)}")
            raise

    def _load_cache(self):
        """Carrega cache de contratos processados"""
        try:
            if Path(MONITOR_CONFIG["cache_file"]).exists():
                with open(MONITOR_CONFIG["cache_file"], 'r') as f:
                    cache_data = json.load(f)
                    self.processed_contracts = set(cache_data.get("processed_contracts", []))
                    self.stats.update(cache_data.get("stats", {}))
                self.logger.info(f" Cache carregado: {len(self.processed_contracts)} contratos processados")
            else:
                self.logger.info(" Nenhum cache encontrado, iniciando vazio")
        except Exception as e:
            self.logger.warning(f" Erro ao carregar cache: {str(e)}")

    def _save_cache(self):
        """Salva cache de contratos processados"""
        try:
            cache_data = {
                "processed_contracts": list(self.processed_contracts),
                "stats": self.stats,
                "last_updated": datetime.now().isoformat()
            }
            with open(MONITOR_CONFIG["cache_file"], 'w') as f:
                json.dump(cache_data, f, indent=2, default=str)
            self.logger.debug(" Cache salvo com sucesso")
        except Exception as e:
            self.logger.error(f" Erro ao salvar cache: {str(e)}")

    def _get_poll_interval(self) -> int:
        """Calcula intervalo de polling baseado na atividade recente"""
        now = datetime.now()
        time_since_activity = (now - self.last_activity).total_seconds()

        if time_since_activity < 300:  # 5 minutos
            return MONITOR_CONFIG["poll_interval_fast"]
        elif time_since_activity < 3600:  # 1 hora
            return MONITOR_CONFIG["poll_interval_normal"]
        else:
            return MONITOR_CONFIG["poll_interval_slow"]

    def _check_new_contracts(self) -> List[Dict]:
        """Verifica se h novos contratos no S3"""
        try:
            self.logger.debug(" Verificando novos contratos no S3...")
            files = self.s3_helper.list_files_in_folder(AWS_CONFIG["contracts_folder"])

            new_contracts = []
            for file_info in files:
                filename = file_info['key']
                if (filename.lower().endswith('.pdf') and
                    filename not in self.processed_contracts and
                    not filename.startswith(f"{AWS_CONFIG['contracts_folder']}audit/")):

                    # Verificar se tem dados extrados
                    if hasattr(file_info, 'get') and 'extracted_name' in file_info:
                        new_contracts.append(file_info)
                        self.logger.info(f" Novo contrato detectado: {filename}")
                    else:
                        # Tentar extrair dados
                        contract_data = self.s3_helper.get_latest_contract(AWS_CONFIG["contracts_folder"])
                        if contract_data and contract_data.get('extracted_name'):
                            new_contracts.append(contract_data)
                            self.logger.info(f" Novo contrato detectado: {filename}")

            self.stats["last_check"] = datetime.now()
            return new_contracts

        except Exception as e:
            self.logger.error(f" Erro ao verificar contratos: {str(e)}")
            self.stats["errors"] += 1
            return []

    def _process_contract(self, contract_info: Dict) -> bool:
        """Processa um contrato individual"""
        filename = contract_info['key']
        contract_name = filename.replace(AWS_CONFIG["contracts_folder"], '').replace('.pdf', '')

        self.logger.info(f" Processando contrato: {contract_name}")

        # Extrair dados se necessrio
        if 'extracted_name' not in contract_info or not contract_info['extracted_name']:
            self.logger.debug(" Extraindo dados automaticamente...")
            fresh_data = self.s3_helper.get_latest_contract(AWS_CONFIG["contracts_folder"])
            if fresh_data and fresh_data.get('extracted_name'):
                contract_info.update(fresh_data)

        signer_name = contract_info.get('extracted_name')
        signer_email = contract_info.get('extracted_email')

        if not signer_name or not signer_email:
            self.logger.error(f" No foi possvel extrair nome/email do contrato: {contract_name}")
            return False

        # Importar aqui para evitar problemas de inicializao
        from contract_signing_api import create_signing_envelope

        # Tentar processar com retries
        for attempt in range(MONITOR_CONFIG["max_retries"]):
            try:
                self.logger.debug(f" Tentativa {attempt + 1}/{MONITOR_CONFIG['max_retries']} para {contract_name}")

                result = create_signing_envelope(
                    signer_email=signer_email,
                    signer_name=signer_name,
                    contract_name=contract_name,
                    auto_extract=False  # J temos os dados
                )

                if result["success"]:
                    self.logger.info(f" Contrato processado com sucesso: {contract_name}")
                    self.logger.info(f" Envelope ID: {result['envelope_id']}")
                    self.logger.info(f" Link: {result['signing_url'][:50]}...")

                    # Salvar resultado
                    self._save_processing_result(contract_info, result)
                    self.stats["contracts_processed"] += 1
                    self.last_activity = datetime.now()
                    return True
                else:
                    self.logger.warning(f" Falha no processamento: {result['message']}")

            except Exception as e:
                self.logger.warning(f" Erro na tentativa {attempt + 1}: {str(e)}")

            if attempt < MONITOR_CONFIG["max_retries"] - 1:
                time.sleep(MONITOR_CONFIG["retry_delay"])

        self.logger.error(f" Falha definitiva no processamento de: {contract_name}")
        self.stats["errors"] += 1
        return False

    def _save_processing_result(self, contract_info: Dict, result: Dict):
        """Salva resultado do processamento"""
        try:
            result_data = {
                "contract_info": contract_info,
                "processing_result": result,
                "processed_at": datetime.now().isoformat(),
                "monitor_version": "1.0"
            }

            filename = f"{contract_info['key'].replace('/', '_').replace('.pdf', '')}_result.json"
            filepath = Path(MONITOR_CONFIG["processed_dir"]) / filename

            with open(filepath, 'w') as f:
                json.dump(result_data, f, indent=2, default=str)

            self.logger.debug(f" Resultado salvo: {filepath}")

        except Exception as e:
            self.logger.warning(f" Erro ao salvar resultado: {str(e)}")

    def _print_stats(self):
        """Imprime estatsticas do sistema"""
        runtime = datetime.now() - self.stats["start_time"]
        hours = runtime.total_seconds() / 3600

        print("\n" + "="*60)
        print(" ESTATSTICAS DO MONITOR")
        print("="*60)
        print(f"  Tempo de execuo: {runtime}")
        print(f" Contratos processados: {self.stats['contracts_processed']}")
        print(f" Erros: {self.stats['errors']}")
        print(f" ltima verificao: {self.stats.get('last_check', 'Nunca')}")
        print(f" Taxa de processamento: {self.stats['contracts_processed']/hours:.2f} contratos/hora")
        print(f" Cache: {len(self.processed_contracts)} contratos rastreados")
        print("="*60 + "\n")

    def _signal_handler(self, signum, frame):
        """Tratamento de sinais para shutdown graceful"""
        self.logger.info(" Sinal de shutdown recebido, finalizando...")
        self.running = False

    def run(self):
        """Loop principal de monitoramento"""
        self.logger.info(" Iniciando monitoramento contnuo...")

        try:
            while self.running:
                # Verificar novos contratos
                new_contracts = self._check_new_contracts()

                # Processar contratos encontrados
                for contract in new_contracts:
                    if self._process_contract(contract):
                        # Marcar como processado
                        filename = contract['key']
                        self.processed_contracts.add(filename)
                        self._save_cache()

                # Calcular prximo intervalo
                interval = self._get_poll_interval()

                if new_contracts:
                    self.logger.info(f" {len(new_contracts)} contratos processados. Prxima verificao em {interval}s")
                else:
                    self.logger.debug(f" Nenhum novo contrato. Prxima verificao em {interval}s")

                # Aguardar antes da prxima verificao
                time.sleep(interval)

        except KeyboardInterrupt:
            self.logger.info(" Monitoramento interrompido pelo usurio")
        except Exception as e:
            self.logger.error(f" Erro crtico no monitoramento: {str(e)}")
        finally:
            self._save_cache()
            self._print_stats()
            self.logger.info(" Monitor finalizado")

def main():
    """Funo principal"""
    monitor = ContratoMonitor()
    monitor.run()

if __name__ == "__main__":
    main()
