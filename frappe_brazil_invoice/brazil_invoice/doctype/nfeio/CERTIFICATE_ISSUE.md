# NFe.io Certificate Issue

## Current Status: Certificate Expired ⚠️

### Problem
The NFe.io integration tests are failing with the following error:
```
'message': 'Certificate expired'
```

### Error Details
- **Event Type**: `SignAndUploadBatchXmlWithFailed`
- **Status**: `UnprocessableEntity`
- **Root Cause**: The digital certificate (e-CNPJ or e-CPF) configured in the NFe.io company account has expired
- **Impact**: Cannot issue fiscal invoices (NF-e) until certificate is renewed

### How to Fix

#### 1. Renew the Digital Certificate
The digital certificate must be renewed through a Brazilian Certificate Authority (CA):
- Common CAs: Certisign, Serasa, Valid, Soluti
- Process: Purchase and install a new A1 or A3 certificate
- Required: Valid CNPJ/CPF and business documentation

#### 2. Upload Certificate to NFe.io
Once renewed, upload the certificate to NFe.io:
1. Log in to NFe.io dashboard
2. Go to Company Settings
3. Navigate to Certificate section
4. Upload the new .pfx certificate file
5. Enter the certificate password

#### 3. Test Environment Configuration
For homologation/test environment:
- Use NFe.io test environment credentials
- Ensure certificate is valid for the test CNPJ: 99999999000191
- Verify certificate expiration date

### Expected Behavior
After certificate renewal:
- Invoice status should progress: `Created` → `Queued` → `Processing` → `Issued`
- Tests should pass with 0 failures
- All 12 tests should complete successfully

### Current Test Configuration
- **Max Retries**: 10 attempts
- **Retry Delay**: 2 seconds per attempt
- **Total Wait Time**: Up to 20 seconds per invoice

### API Error Response Example
```json
{
  "lastEvents": {
    "events": [
      {
        "type": "SignAndUploadBatchXmlWithFailed",
        "data": {
          "status": "UnprocessableEntity",
          "message": "Certificate expired",
          "createdOn": "2025-12-28T15:29:21.5569318+00:00"
        }
      }
    ]
  }
}
```

### Related Documentation
- NFe.io API: https://api.nfse.io/docs
- Brazilian e-CNPJ certificate guide: https://www.gov.br/iti
- NFe.io certificate management: https://api.nfse.io/docs/certificate

### Contact
For certificate renewal support:
- NFe.io Support: https://nfe.io/suporte
- Brazilian ICP (PKI): https://www.iti.gov.br

---
**Last Updated**: December 28, 2025
**Tested With**: NFe.io API v2, Company ID: 8cf2227894b546a1a1da3ae53bbf5277
