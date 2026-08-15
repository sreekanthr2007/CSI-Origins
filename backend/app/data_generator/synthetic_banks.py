"""Synthetic Indian Bank Registry, Customer Accounts, and Erdős-Rényi Transaction Generator."""
import random
import datetime
from typing import List, Dict, Any, Optional, TypedDict
import networkx as nx
from backend.app.config import settings

# 10 Simulated Indian Banks
BANK_METADATA: List[Dict[str, str]] = [
    {"name": "State Bank of India", "ifsc_prefix": "SBIN", "id": "bank_sbi"},
    {"name": "HDFC Bank", "ifsc_prefix": "HDFC", "id": "bank_hdfc"},
    {"name": "ICICI Bank", "ifsc_prefix": "ICIC", "id": "bank_icici"},
    {"name": "Axis Bank", "ifsc_prefix": "UTIB", "id": "bank_axis"},
    {"name": "Punjab National Bank", "ifsc_prefix": "PUNB", "id": "bank_pnb"},
    {"name": "Bank of Baroda", "ifsc_prefix": "BARB", "id": "bank_bob"},
    {"name": "Canara Bank", "ifsc_prefix": "CNRB", "id": "bank_canara"},
    {"name": "Yes Bank", "ifsc_prefix": "YESB", "id": "bank_yes"},
    {"name": "Kotak Mahindra Bank", "ifsc_prefix": "KKBK", "id": "bank_kotak"},
    {"name": "IndusInd Bank", "ifsc_prefix": "INDB", "id": "bank_indusind"},
]

FIRST_NAMES = [
    "Rajesh", "Priya", "Amit", "Sneha", "Rahul", "Ananya", "Vikram", "Deepika",
    "Suresh", "Pooja", "Arjun", "Kavita", "Rohan", "Meera", "Manoj", "Divya",
    "Sunil", "Ritu", "Alok", "Neha", "Varun", "Swati", "Sanjay", "Anjali"
]

LAST_NAMES = [
    "Kumar", "Sharma", "Verma", "Patel", "Singh", "Gupta", "Iyer", "Reddy",
    "Joshi", "Mehta", "Nair", "Das", "Rao", "Choudhury", "Bose", "Pillai"
]


class BankMetadata(TypedDict):
    id: str
    name: str
    ifsc_prefix: str


class Account(TypedDict):
    account_number: str
    ifsc_code: str
    bank_id: str
    bank_name: str
    customer_name: str
    kyc_status: str
    declared_income: float
    account_age_days: int
    opening_date: str
    is_dormant: bool


class Transaction(TypedDict):
    sender_account: str
    receiver_account: str
    sender_bank_id: str
    receiver_bank_id: str
    amount: float
    timestamp: str
    is_interbank: bool
    local_risk_score: float


def generate_banks(num_banks: Optional[int] = None) -> List[Dict[str, Any]]:
    """Return simulated bank profiles."""
    count = num_banks or len(BANK_METADATA)
    return [dict(b) for b in BANK_METADATA[:count]]


def generate_accounts(bank: Dict[str, Any], count: int, seed: Optional[int] = None) -> List[Dict[str, Any]]:
    """Generate realistic Indian accounts for a specified bank."""
    if seed is not None:
        random.seed(seed)

    accounts: List[Dict[str, Any]] = []
    prefix = bank["ifsc_prefix"]
    bank_id = bank["id"]
    bank_name = bank["name"]

    now = datetime.datetime.now(datetime.timezone.utc)

    for i in range(count):
        branch_code = f"{random.randint(1000, 9999):06d}"
        ifsc_code = f"{prefix}0{branch_code}"
        
        # 11-16 digit account number
        suffix_digits = f"{random.randint(10000000, 99999999)}{i:03d}"
        account_number = f"{prefix}{suffix_digits[:10]}"
        
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        kyc_status = "verified" if random.random() < 0.90 else "pending"
        
        age_days = random.randint(10, 1800)
        opening_date = (now - datetime.timedelta(days=age_days)).strftime("%Y-%m-%d")
        
        # 5% dormant accounts
        is_dormant = random.random() < 0.05
        
        # ₹15k to ₹1,50,000 monthly income
        declared_income = float(random.randint(15, 150) * 1000)

        accounts.append({
            "account_number": account_number,
            "ifsc_code": ifsc_code,
            "bank_id": bank_id,
            "bank_name": bank_name,
            "customer_name": name,
            "kyc_status": kyc_status,
            "declared_income": declared_income,
            "account_age_days": age_days,
            "opening_date": opening_date,
            "is_dormant": is_dormant
        })

    return accounts


def generate_transactions(
    accounts: List[Dict[str, Any]],
    num_edges: int,
    seed: int = 42
) -> List[Dict[str, Any]]:
    """
    Generate Erdős-Rényi directed inter-bank transactions over 30 days.
    Ensures sender and receiver belong to different institutions.
    """
    random.seed(seed)
    num_accounts = len(accounts)
    if num_accounts < 2:
        return []

    # Partition accounts by bank_id for rapid inter-bank selection
    bank_to_accounts: Dict[str, List[Dict[str, Any]]] = {}
    for acc in accounts:
        bank_to_accounts.setdefault(acc["bank_id"], []).append(acc)

    banks_list = list(bank_to_accounts.keys())
    if len(banks_list) < 2:
        return []

    now = datetime.datetime.now(datetime.timezone.utc)
    transactions: List[Dict[str, Any]] = []

    for _ in range(num_edges):
        # Pick two distinct banks
        sender_bank, receiver_bank = random.sample(banks_list, 2)
        sender = random.choice(bank_to_accounts[sender_bank])
        receiver = random.choice(bank_to_accounts[receiver_bank])

        # Amount distribution: 95% regular (₹100 - ₹50,000), 5% high value (₹50,000 - ₹5,00,000)
        if random.random() < 0.95:
            amount = round(random.uniform(100.0, 50000.0), 2)
        else:
            amount = round(random.uniform(50000.0, 500000.0), 2)

        # Temporal distribution over 30 days, heavily weighted towards last 7 days
        days_back = int(random.triangular(0, 30, 4))
        
        # Business hours bias: 9 AM to 9 PM IST (03:30 to 15:30 UTC)
        hour = random.choice([9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]) if random.random() < 0.85 else random.randint(0, 23)
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        
        tx_time = now - datetime.timedelta(days=days_back, hours=now.hour - hour, minutes=now.minute - minute, seconds=now.second - second)
        timestamp_str = tx_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Baseline benign local risk score
        local_risk = round(random.uniform(0.01, 0.25), 4)

        transactions.append({
            "sender_account": sender["account_number"],
            "sender_ifsc": sender["ifsc_code"],
            "receiver_account": receiver["account_number"],
            "receiver_ifsc": receiver["ifsc_code"],
            "sender_bank_id": sender["bank_id"],
            "receiver_bank_id": receiver["bank_id"],
            "amount": amount,
            "timestamp": timestamp_str,
            "is_interbank": True,
            "local_risk_score": local_risk,
            "is_mule_edge": False
        })

    # Sort transactions chronologically
    transactions.sort(key=lambda x: x["timestamp"])
    return transactions
