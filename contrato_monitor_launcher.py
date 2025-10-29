#!/usr/bin/env python3
"""
Launcher para o Sistema de Monitoramento de Contratos

Este script facilita o uso do monitor com diferentes modos de operação:
- Modo daemon: monitoramento contínuo
- Modo check: verificar uma vez e sair
- Modo service: executar como serviço do Windows/Linux
"""

import argparse
import sys
import os
from pathlib import Path

def run_daemon():
    """Executa o monitor em modo daemon"""
    print("Iniciando Monitor de Contratos em modo DAEMON...")
    print("Pressione Ctrl+C para parar")
    print("-" * 50)

    # Importar e executar
    from contrato_monitor import main
    main()

def run_check():
    """Executa verificação única"""
    print("Executando verificacao unica de contratos...")

    try:
        from contrato_monitor import ContratoMonitor

        monitor = ContratoMonitor()
        new_contracts = monitor._check_new_contracts()

        if new_contracts:
            print(f"Encontrados {len(new_contracts)} novos contratos:")
            for contract in new_contracts:
                filename = contract['key'].replace(monitor.s3_helper.bucket_name + '/', '')
                print(f"  • {filename}")
                if contract.get('extracted_name'):
                    print(f"    Nome: {contract['extracted_name']} <{contract['extracted_email']}>")
        else:
            print("Nenhum novo contrato encontrado")

    except Exception as e:
        print(f"Erro: {str(e)}")
        return 1

    return 0

def run_process_all():
    """Processa todos os contratos não processados"""
    print("Processando todos os contratos pendentes...")

    try:
        from contrato_monitor import ContratoMonitor

        monitor = ContratoMonitor()
        new_contracts = monitor._check_new_contracts()

        if not new_contracts:
            print("Nenhum contrato pendente para processar")
            return 0

        print(f"Encontrados {len(new_contracts)} contratos para processar")

        processed = 0
        errors = 0

        for contract in new_contracts:
            filename = contract['key'].replace(monitor.s3_helper.bucket_name + '/', '')
            print(f"\nProcessando: {filename}")

            if monitor._process_contract(contract):
                monitor.processed_contracts.add(contract['key'])
                processed += 1
                print(f"Sucesso: {filename}")
            else:
                errors += 1
                print(f"Falhou: {filename}")

        monitor._save_cache()

        print("\nRESULTADO:")
        print(f"Processados: {processed}")
        print(f"Erros: {errors}")

        return 0 if errors == 0 else 1

    except Exception as e:
        print(f"Erro critico: {str(e)}")
        return 1

def show_stats():
    """Mostra estatísticas do sistema"""
    try:
        from contrato_monitor import MONITOR_CONFIG
        import json

        cache_file = MONITOR_CONFIG["cache_file"]
        if Path(cache_file).exists():
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)

            stats = cache_data.get("stats", {})
            processed = cache_data.get("processed_contracts", [])

            print("ESTATISTICAS DO SISTEMA")
            print("=" * 40)
            print(f"Contratos processados: {stats.get('contracts_processed', 0)}")
            print(f"Erros: {stats.get('errors', 0)}")
            print(f"Total rastreados: {len(processed)}")
            print(f"Ultima verificacao: {stats.get('last_check', 'Nunca')}")

            if processed:
                print(f"\nUltimos 5 processados:")
                for contract in processed[-5:]:
                    filename = contract.replace('contratos-gerados/', '')
                    print(f"  • {filename}")
        else:
            print("Nenhum dado de cache encontrado")

    except Exception as e:
        print(f"Erro ao ler estatisticas: {str(e)}")
        return 1

    return 0

def clear_cache():
    """Limpa o cache do sistema"""
    try:
        from contrato_monitor import MONITOR_CONFIG

        cache_file = MONITOR_CONFIG["cache_file"]
        if Path(cache_file).exists():
            os.remove(cache_file)
            print(f"Cache limpo: {cache_file}")
        else:
            print("Nenhum cache encontrado")

        processed_dir = MONITOR_CONFIG["processed_dir"]
        if Path(processed_dir).exists():
            import shutil
            shutil.rmtree(processed_dir)
            print(f"Resultados limpos: {processed_dir}")

    except Exception as e:
        print(f"Erro ao limpar cache: {str(e)}")
        return 1

    return 0

def main():
    parser = argparse.ArgumentParser(
        description='Monitor de Contratos - Sistema de processamento automático',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXEMPLOS DE USO:

  # Monitoramento contínuo (daemon)
  python contrato_monitor_launcher.py daemon

  # Verificar uma vez se há novos contratos
  python contrato_monitor_launcher.py check

  # Processar todos os contratos pendentes
  python contrato_monitor_launcher.py process-all

  # Ver estatísticas
  python contrato_monitor_launcher.py stats

  # Limpar cache
  python contrato_monitor_launcher.py clear-cache
        """
    )

    parser.add_argument(
        'command',
        choices=['daemon', 'check', 'process-all', 'stats', 'clear-cache'],
        help='Comando a executar'
    )

    args = parser.parse_args()

    # Executar comando selecionado
    if args.command == 'daemon':
        return run_daemon()
    elif args.command == 'check':
        return run_check()
    elif args.command == 'process-all':
        return run_process_all()
    elif args.command == 'stats':
        return show_stats()
    elif args.command == 'clear-cache':
        return clear_cache()

if __name__ == "__main__":
    sys.exit(main())
