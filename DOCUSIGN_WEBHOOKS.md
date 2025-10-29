# Configuração de Webhooks DocuSign

Este documento explica como configurar webhooks no DocuSign para receber notificações quando contratos são assinados e atualizar automaticamente o Google Sheets.

## 📋 Visão Geral

Quando um contrato é assinado no DocuSign, o sistema:
1. ✅ Recebe notificação via webhook
2. ✅ Atualiza o status no Google Sheets para "assinado"
3. ✅ Envia email de notificação (opcional)

## 🔧 Configuração no DocuSign

### 1. Acesse o DocuSign Admin
- Vá para [DocuSign Admin](https://admin.docusign.com/)
- Entre com sua conta

### 2. Configure Connect
- Vá para **Integrations** → **Connect**
- Clique em **Add Configuration**

### 3. Configurações do Webhook
```
Name: Contratos INNOVATIS Webhook
URL to Publish: https://sua-api.com/webhook/docusign
Include HMAC Signature: Não (para desenvolvimento)
Trigger Events:
  - Envelope Complete
  - Envelope Declined (opcional)
  - Envelope Voided (opcional)

Include Documents: Não
Require Acknowledgement: Sim
```

### 4. Teste o Webhook
- Use ferramentas como [ngrok](https://ngrok.com/) para expor localhost
- Configure a URL: `https://abcd1234.ngrok.io/webhook/docusign`
- Teste com envelopes reais

## 📊 Formato do Payload

O DocuSign envia webhooks no seguinte formato:

```json
{
  "event": "envelope-completed",
  "data": {
    "envelopeId": "b8f2d556-99c1-4251-ae49-decab5ec9fe1",
    "status": "completed",
    "statusChangedDateTime": "2025-10-28T13:47:30.0000000Z",
    "documents": [
      {
        "documentId": "1",
        "name": "contrato.pdf",
        "type": "content"
      }
    ],
    "recipients": {
      "signers": [
        {
          "recipientId": "1",
          "email": "cliente@email.com",
          "name": "Cliente Exemplo",
          "status": "completed",
          "signedDateTime": "2025-10-28T13:47:25.0000000Z"
        }
      ]
    }
  }
}
```

## 🎯 Campos Atualizados no Google Sheets

Quando um contrato é assinado, o sistema atualiza:

| Campo | Valor | Descrição |
|-------|-------|-----------|
| `contrato_assinado` | `"assinado"` | Status de assinatura |
| `data_criacao` | Timestamp | Data/hora da conclusão |

## 📧 Notificações por Email

Configure as variáveis de ambiente para receber notificações:

```bash
# config.env
NOTIFICATION_EMAIL=seu-email@exemplo.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=seu-email@gmail.com
SMTP_PASSWORD=sua-senha-app-gmail
```

### Exemplo de Email Recebido:

```
Assunto: Contrato Assinado - Cliente Exemplo

Contrato assinado com sucesso!

Detalhes:
- Nome: Cliente Exemplo
- Email: cliente@email.com
- Envelope ID: b8f2d556-99c1-4251-ae49-decab5ec9fe1
- Data de conclusão: 2025-10-28T13:47:30.0000000Z

O contrato foi marcado como 'assinado' no Google Sheets.
```

## 🧪 Testes

### Teste Local
```bash
# Testar webhook localmente
python test_docusign_webhook.py --local

# Testar endpoint da API
python test_docusign_webhook.py
```

### Teste de Produção
1. Configure o webhook no DocuSign com a URL de produção
2. Envie um envelope de teste
3. Verifique se o Google Sheets foi atualizado
4. Confirme se o email foi enviado

## 🔍 Monitoramento

### Logs da API
```
2025-10-28 13:47:31 - INFO - DocuSign webhook received: envelope-completed
2025-10-28 13:47:36 - INFO - Contract status updated: Cliente Exemplo (cliente@email.com) -> assinado
2025-10-28 13:47:36 - INFO - Notification email sent to: seu-email@exemplo.com
```

### Verificação no Google Sheets
Após assinatura, verifique se:
- ✅ Coluna `contrato_assinado` mostra "assinado"
- ✅ Data de conclusão foi registrada
- ✅ Status permanece "Enviado"

## 🚨 Troubleshooting

### Webhook não está sendo chamado
- ✅ Verifique se a URL está acessível publicamente
- ✅ Confirme se o DocuSign Connect está ativo
- ✅ Verifique logs da API

### Status não está sendo atualizado
- ✅ Verifique conexão com Google Sheets
- ✅ Confirme se o envelope ID existe no Google Sheets
- ✅ Verifique se a coluna `contrato_assinado` existe

### Email não está sendo enviado
- ✅ Verifique configurações SMTP
- ✅ Confirme credenciais de email
- ✅ Verifique se a porta SMTP está aberta

## 📚 Referências

- [DocuSign Connect Documentation](https://developers.docusign.com/docs/connect/)
- [Webhook Events Reference](https://developers.docusign.com/docs/connect/connect-reference/event-triggers/)
- [Envelope Status Values](https://developers.docusign.com/docs/esign-rest-api/reference/envelopes/envelope/status/)
