#!/usr/bin/env python3
"""Verify actual local report-file bytes against declared disclosure SHA-256.

No network, no PDF scraping, no claim that the file was issued by PSX.
Never publishes raw documents or promotes a stock to trade eligibility.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

MAX_REPORT_BYTES = 40 * 1024 * 1024

def verify(disclosure_report, reports_dir=None):
    reviews = disclosure_report.get('reviews')
    if not isinstance(reviews, list):
        raise ValueError('fundamental review must contain reviews array')
    root = Path(reports_dir).resolve() if reports_dir else None
    items = []
    for review in reviews:
        symbol = review['symbol']
        digest = review.get('report_sha256')
        status = 'NO_DISCLOSURE' if review['status'] == 'DISCLOSURE_MISSING' else 'REPORT_FILE_NOT_PROVIDED'
        result = {'symbol': symbol, 'status': status, 'document_bytes_verified': False,
                  'issuer_authenticity_verified': False, 'financial_figures_verified': False,
                  'trade_eligible': False}
        if digest is not None and root:
            if not symbol.isalnum() or len(symbol) > 12:
                raise ValueError('invalid symbol in report')
            path = root / (symbol + '.pdf')
            # Resolve every path, preventing symlinks from redirecting outside configured folder.
            if path.is_symlink():
                raise ValueError('symlinked disclosure file rejected')
            resolved = path.resolve()
            if not resolved.is_relative_to(root):
                raise ValueError('report path escapes configured folder')
            if path.is_file():
                size = path.stat().st_size
                if size <= 0 or size > MAX_REPORT_BYTES:
                    result['status'] = 'REPORT_SIZE_INVALID'
                else:
                    h=hashlib.sha256()
                    with path.open('rb') as f:
                        magic=f.read(5)
                        if magic != b'%PDF-':
                            result['status'] = 'NOT_A_PDF'
                        else:
                            h.update(magic)
                            while True:
                                chunk=f.read(1024*1024)
                                if not chunk: break
                                h.update(chunk)
                            if h.hexdigest().lower() != digest.lower():
                                result['status'] = 'REPORT_HASH_MISMATCH'
                            else:
                                result['status'] = 'DOCUMENT_BYTES_MATCH'
                                result['document_bytes_verified'] = True
                                result['report_sha256'] = h.hexdigest()
                                result['document_size_bytes'] = size
        items.append(result)
    return {
        'schema_version': '1.0',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'provenance': 'local_file_integrity_only_not_issuer_authentication',
        'not_investment_advice': True,
        'reviews': items,
        'health': {
            'symbols':len(items),
            'document_bytes_verified':sum(x['document_bytes_verified'] for x in items),
            'document_missing':sum(x['status'] in ('NO_DISCLOSURE','REPORT_FILE_NOT_PROVIDED') for x in items),
            'document_errors':sum(x['status'] in ('REPORT_SIZE_INVALID','NOT_A_PDF','REPORT_HASH_MISMATCH') for x in items),
            'issuer_authenticated':0,
            'trade_eligible':0,
        },
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--fundamentals',default='publish/fundamental_review.json')
    parser.add_argument('--reports-dir',help='Optional operator-provided local directory of SYMBOL.pdf')
    parser.add_argument('--out',default='publish/financial_document_integrity.json')
    args=parser.parse_args()
    fundamental=json.loads(Path(args.fundamentals).read_text())
    result=verify(fundamental,args.reports_dir)
    dest=Path(args.out)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print('Financial document integrity:',result['health'])
if __name__ == '__main__':
    main()
