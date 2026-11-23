"""A tesztek környezeti változói, az app importja előtt."""
import os
import tempfile

os.environ.update({
    "OUR_COMPANY_NAME": "Nordwind Solutions Kft.",
    "OUR_TAX_IDS": "26481937-2-43,HU26481937",
    "DATA_DIR": tempfile.mkdtemp(prefix="invoice-tests-"),
    "MNB_ENDPOINT": "http://mnb.invalid/arfolyamok.asmx",
})
