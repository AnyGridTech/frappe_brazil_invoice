# Copyright (c) 2025, AnyGridTech and Contributors
# See license.txt

"""
Shared Helper Functions and Data for Product Invoice Tests

This module contains shared utilities, helper functions, and test data
used by both test_product_invoice_mocked.py and test_product_invoice_real_api.py
"""

import uuid
import frappe
from frappe_brazil_invoice.brazil_invoice.doctype.product_invoice.product_invoice import (
    create_invoice,
)


# =============================================================================
# Token and Tracking
# =============================================================================

def get_test_run_token():
    """Get or create a test run token for tracking invoices"""
    if not hasattr(frappe.flags, 'TEST_RUN_TOKEN') or not frappe.flags.TEST_RUN_TOKEN:
        frappe.flags.TEST_RUN_TOKEN = f"RUN-{uuid.uuid4().hex[:12]}"
    return frappe.flags.TEST_RUN_TOKEN


# =============================================================================
# Invoice Creation
# =============================================================================

def create_test_invoice_with_token(*args, **kwargs):
    """
    Wrapper around create_invoice that automatically adds TEST_RUN_TOKEN
    to additional_information for tracking test run invoices.
    """
    test_token = get_test_run_token()
    
    if test_token:
        # Get existing additional_information or create empty string
        additional_info = kwargs.get("additional_information", "")

        # Append test run token marker
        token_marker = f"[TEST_RUN:{test_token}]"
        if additional_info:
            kwargs["additional_information"] = f"{additional_info} {token_marker}"
        else:
            kwargs["additional_information"] = token_marker

    # Call the original create_invoice function
    return create_invoice(*args, **kwargs)


# =============================================================================
# Cleanup Functions
# =============================================================================

def cleanup_test_invoices():
    """
    Delete all existing test invoices with test token markers.
    
    Only deletes invoices that have a test token marker in additional_information.
    This ensures real invoices are never accidentally deleted.
    
    Returns:
        int: Number of invoices deleted
    """
    frappe.set_user("Administrator")
    
    # Get count before deletion for reporting
    count_before = frappe.db.sql(
        """SELECT COUNT(*) FROM `tabProduct Invoice` 
           WHERE additional_information LIKE '%[TEST_RUN:%'"""
    )[0][0]
    
    # Delete invoices with test run token in additional_information
    frappe.db.sql(
        """DELETE FROM `tabProduct Invoice` 
           WHERE additional_information LIKE '%[TEST_RUN:%'"""
    )
    frappe.db.commit()
    
    print(f"✓ Cleared {count_before} test invoice(s) with [TEST_RUN:*] markers")
    return count_before


# =============================================================================
# Item and Serial Number Creation
# =============================================================================

def create_test_item(
    item_code, item_name, rate, ncm_code, description=None, item_group="Products"
):
    """Helper function to create a test item"""
    if frappe.db.exists("Item", item_code):
        return frappe.get_doc("Item", item_code)

    item = frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": item_code,
            "item_name": item_name,
            "item_group": item_group,
            "stock_uom": "Unit",
            "is_stock_item": 1,
            "valuation_rate": rate,
            "standard_rate": rate,
            "description": description or item_name,
            "has_serial_no": 1,  # Enable serial numbers for tracking
            "ncm": ncm_code,
        }
    )
    item.insert(ignore_permissions=True)
    frappe.db.commit()
    return item


def create_test_serial_no(item_code, serial_no=None):
    """Create a serial number for an item"""
    if not serial_no:
        serial_no = generate_random_serial_number()

    # Check if serial number already exists
    if frappe.db.exists("Serial No", serial_no):
        return frappe.get_doc("Serial No", serial_no)

    # Get a valid company
    company = frappe.db.get_single_value("Global Defaults", "default_company")
    if not company or not frappe.db.exists("Company", company):
        # Try to get any company
        company = frappe.db.get_value("Company", filters={}, fieldname="name")
        if not company:
            # Create a test company if none exists
            test_company = frappe.get_doc(
                {
                    "doctype": "Company",
                    "company_name": "Test Company",
                    "abbr": "TC",
                    "default_currency": "BRL",
                    "country": "Brazil",
                }
            )
            test_company.insert(ignore_permissions=True)
            company = test_company.name

    serial = frappe.get_doc(
        {
            "doctype": "Serial No",
            "serial_no": serial_no,
            "item_code": item_code,
            "company": company,
            "status": "Active",
        }
    )
    serial.insert(ignore_permissions=True)
    frappe.db.commit()
    return serial


# =============================================================================
# Random Data Generators
# =============================================================================

def generate_random_serial_number():
    """Generate a serial number with format AAA123123A (3 letters + 7 letters/numbers)"""
    import random
    import string

    # First 3 characters: uppercase letters
    prefix = "".join(random.choices(string.ascii_uppercase, k=3))

    # Next 7 characters: uppercase letters or numbers
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=7))

    return f"{prefix}{suffix}"


def generate_random_phone_number():
    """Generate a random Brazilian phone number matching Frappe Phone field validation

    Returns:
        str: Brazilian phone number with format +55-XX9XXXXXXXX
    """
    import random

    # Brazilian area codes
    area_code = random.choice(
        ["11", "21", "31", "41", "51", "61", "71", "81", "85", "91"]
    )
    # Generate 8 digits (9XXXXXXX format for mobile)
    phone_number = f"9{random.randint(10000000, 99999999)}"
    return f"+55-{area_code}{phone_number}"


def generate_random_client(client_type=None):
    """Generate random client information for PF (individual) or PJ (company)

    Args:
        client_type (str, optional): 'Company' for PJ or 'Individual' for PF.
                                     If None, randomly chosen.

    Returns:
        dict: Dictionary with client_name, email, phone, client_id_number,
              icms_contributor, client_type, and state_registration
    """
    import random

    # Randomly choose if not specified
    if client_type is None:
        client_type = random.choice(["Company", "Individual"])

    # Generate base data
    first_names = [
        "João",
        "Maria",
        "José",
        "Ana",
        "Pedro",
        "Paula",
        "Carlos",
        "Juliana",
        "Lucas",
        "Fernanda",
    ]
    last_names = [
        "Silva",
        "Santos",
        "Oliveira",
        "Souza",
        "Lima",
        "Pereira",
        "Costa",
        "Ferreira",
        "Alves",
        "Rodrigues",
    ]

    def generate_cpf():
        """Generate a valid CPF number"""

        def calculate_digit(digits):
            s = sum(int(d) * w for d, w in zip(digits, range(len(digits) + 1, 1, -1)))
            digit = 11 - (s % 11)
            return 0 if digit > 9 else digit

        # Generate first 9 digits
        cpf = [random.randint(0, 9) for _ in range(9)]
        # Calculate verification digits
        cpf.append(calculate_digit(cpf))
        cpf.append(calculate_digit(cpf))
        # Format as XXX.XXX.XXX-XX
        cpf_str = "".join(map(str, cpf))
        return f"{cpf_str[:3]}.{cpf_str[3:6]}.{cpf_str[6:9]}-{cpf_str[9:]}"

    def generate_cnpj():
        """Generate a valid CNPJ number"""

        def calculate_digit(digits, weights):
            s = sum(int(d) * w for d, w in zip(digits, weights))
            digit = 11 - (s % 11)
            return 0 if digit > 9 else digit

        # Generate first 8 digits (base) + 4 digits (branch)
        cnpj = [random.randint(0, 9) for _ in range(8)] + [0, 0, 0, 1]
        # Calculate first verification digit
        weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        cnpj.append(calculate_digit(cnpj, weights1))
        # Calculate second verification digit
        weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        cnpj.append(calculate_digit(cnpj, weights2))
        # Format as XX.XXX.XXX/XXXX-XX
        cnpj_str = "".join(map(str, cnpj))
        return f"{cnpj_str[:2]}.{cnpj_str[2:5]}.{cnpj_str[5:8]}/{cnpj_str[8:12]}-{cnpj_str[12:]}"

    if client_type == "Company":
        # Generate company (PJ) data
        company_suffixes = ["Ltda", "S.A.", "ME", "EPP", "EIRELI"]
        business_types = [
            "Comércio",
            "Indústria",
            "Serviços",
            "Tecnologia",
            "Distribuidora",
        ]

        client_name = f"{random.choice(business_types)} {random.choice(last_names)} {random.choice(company_suffixes)}"
        client_id_number = generate_cnpj()
        icms_contributor = "Taxpayer"  # Companies are typically taxpayers
        # Generate state registration (9 digits)
        state_registration = "".join([str(random.randint(0, 9)) for _ in range(9)])
    else:
        # Generate individual (PF) data
        client_name = f"{random.choice(first_names)} {random.choice(last_names)}"
        client_id_number = generate_cpf()
        icms_contributor = "Non-Taxpayer"  # Individuals are typically non-taxpayers
        state_registration = "ISENTO"  # Exempt for individuals

    # Generate contact info
    email_name = (
        client_name.lower()
        .replace(" ", ".")
        .replace("ltda", "")
        .replace("s.a.", "")
        .replace("me", "")
        .replace("epp", "")
        .replace("eireli", "")
        .strip(".")
    )
    email = f"{email_name}@test.com"

    # Generate Brazilian phone number using helper function
    phone = generate_random_phone_number()

    return {
        "client_name": client_name,
        "email": email,
        "phone": phone,
        "client_id_number": client_id_number,
        "icms_contributor": icms_contributor,
        "client_type": client_type,
        "state_registration": state_registration,
    }


def generate_random_totals():
    """Generate random values for invoice totals

    Returns:
        dict: Dictionary with total_freight, total_discount, total_insurance, other_expenses
    """
    import random

    return {
        "total_freight": round(random.uniform(20.00, 150.00), 2),
        "total_discount": round(random.uniform(0.00, 100.00), 2),
        "total_insurance": round(random.uniform(5.00, 50.00), 2),
        "other_expenses": round(random.uniform(0.00, 30.00), 2),
    }


def generate_random_address(exclude_state=None):
    """Generate random address and contact information for testing

    Args:
        exclude_state (str, optional): State code to exclude from random selection (e.g., "SP").
                                       Use this for interstate invoice testing.

    Returns:
        dict: Dictionary with random address, phone, and location data
    """
    import random

    # Brazilian cities with their data
    cities_data = [
        {
            "city": "São Paulo",
            "state": "SP",
            "cep": "01310-100",
            "ibge": "3550308",
            "neighborhood": [
                "Bela Vista",
                "Centro",
                "Jardins",
                "Pinheiros",
                "Vila Mariana",
            ],
        },
        {
            "city": "Rio de Janeiro",
            "state": "RJ",
            "cep": "20040-020",
            "ibge": "3304557",
            "neighborhood": ["Centro", "Copacabana", "Ipanema", "Leblon", "Botafogo"],
        },
        {
            "city": "Belo Horizonte",
            "state": "MG",
            "cep": "30130-010",
            "ibge": "3106200",
            "neighborhood": [
                "Centro",
                "Savassi",
                "Lourdes",
                "Funcionários",
                "Pampulha",
            ],
        },
        {
            "city": "Curitiba",
            "state": "PR",
            "cep": "80010-010",
            "ibge": "4106902",
            "neighborhood": ["Centro", "Batel", "Água Verde", "Portão", "Bacacheri"],
        },
        {
            "city": "Porto Alegre",
            "state": "RS",
            "cep": "90010-150",
            "ibge": "4314902",
            "neighborhood": [
                "Centro",
                "Moinhos de Vento",
                "Petrópolis",
                "Auxiliadora",
                "Tristeza",
            ],
        },
    ]

    # Filter out excluded state if provided
    if exclude_state:
        cities_data = [city for city in cities_data if city["state"] != exclude_state]
        
        # Ensure we have at least one city after filtering
        if not cities_data:
            raise ValueError(f"No cities available after excluding state: {exclude_state}")

    street_types = ["Rua", "Avenida", "Travessa", "Alameda", "Praça"]
    street_names = [
        "das Flores",
        "do Comércio",
        "Principal",
        "Central",
        "dos Estados",
        "Brasil",
        "Independência",
        "República",
        "Paulista",
        "Atlântica",
        "Ipiranga",
    ]

    # Brazilian first and last names for delivery supervisor
    first_names = [
        "João",
        "Maria",
        "José",
        "Ana",
        "Paulo",
        "Carlos",
        "Pedro",
        "Lucas",
        "Rafael",
        "Fernanda",
    ]
    last_names = [
        "Silva",
        "Santos",
        "Oliveira",
        "Souza",
        "Rodrigues",
        "Ferreira",
        "Costa",
        "Pereira",
        "Almeida",
        "Nascimento",
    ]

    # Select random city
    city_data = random.choice(cities_data)

    # Generate random phone number using helper function
    phone_number = generate_random_phone_number()

    # Generate random address
    street_type = random.choice(street_types)
    street_name = random.choice(street_names)
    address_number = str(random.randint(1, 9999))

    # Generate random responsible person name
    responsible = f"{random.choice(first_names)} {random.choice(last_names)}"

    return {
        "city": city_data["city"],
        "state": city_data["state"],
        "cep": city_data["cep"],
        "ibge": city_data["ibge"],
        "neighborhood": random.choice(city_data["neighborhood"]),
        "address": f"{street_type} {street_name}",
        "address_number": address_number,
        "phone": phone_number,
        "responsible": responsible,
    }


# =============================================================================
# Test Data Arrays
# =============================================================================

items_array = [
    {
        "item_code": "TEST_INVERTER_001",
        "item_name": "Test Inverter 001",
        "rate": 100.00,
        "ncm_code": "8504.40.90",
        "description": "Test Inverter 001 Description",
    },
    {
        "item_code": "TEST_INVERTER_002",
        "item_name": "Test Inverter 002",
        "rate": 150.00,
        "ncm_code": "8504.40.90",
        "description": "Test Inverter 002 Description",
    },
    {
        "item_code": "TEST_INVERTER_003",
        "item_name": "Test Inverter 003",
        "rate": 200.00,
        "ncm_code": "8504.40.90",
        "description": "Test Inverter 003 Description",
    },
]


def get_serial_no_array():
    """Generate serial number array with random serial numbers
    
    Note: Returns a function to generate fresh serial numbers on each call
    to avoid reusing serial numbers across test runs.
    """
    return [
        {
            "item_code": "TEST_INVERTER_001",
            "serial_no": generate_random_serial_number(),
        },
        {
            "item_code": "TEST_INVERTER_002",
            "serial_no": generate_random_serial_number(),
        },
        {
            "item_code": "TEST_INVERTER_003",
            "serial_no": generate_random_serial_number(),
        },
    ]


tax_array = [
    {
        "template_name": "Remessa em Garantia",
        "is_template": 1,
        "operation_type": "Warranty Exchange",
        "origin_icms": "0 - National, except those indicated in codes 3, 4, 5 and 8;",
        "cst_icms": "00 - Fully taxed",
        "icms_rate": 0.00,
        "fcp_rate": 0.00,
        "calculate_automatically_icms": 1,
        "add_other_expenses_icms": 1,
        "add_freight_icms": 1,
        "add_ipi_icms": 1,
        "add_insurance_icms": 1,
        "apply_auto_rate_icms": 0,
        "cst_ipi": "50 - Exit taxed",
        "ipi_rate": 0.00,
        "calculate_automatically_ipi": 1,
        "cst_cofins": "01 - Taxable Operation with Basic Rate",
        "cofins_rate": 7.6,
        "calculate_automatically_cofins": 0,
        "cst_pis": "01 - Taxable Operation with Basic Rate",
        "pis_rate": 1.65,
        "calculate_automatically_pis": 0,
    },
]

test_carriers = [
    {
        "fantasy_name": "Transportadora Teste",
        "company_name": "Transportadora Teste Ltda",
        "cnpj": "12.345.678/0001-90",
        "cep": "01310-100",
        "address": "Avenida Paulista",
        "address_number": "1000",
        "state": "SP",
        "city": "São Paulo",
        "neighborhood": "Bela Vista",
        "ibge": "3550308",
    },
]

serial_no_array = [
    {
        "item_code": "TEST_INVERTER_001",
        "serial_no": generate_random_serial_number(),
    },
    {
        "item_code": "TEST_INVERTER_002",
        "serial_no": generate_random_serial_number(),
    },
    {
        "item_code": "TEST_INVERTER_003",
        "serial_no": generate_random_serial_number(),
    },
]

# =============================================================================
# Display Helpers
# =============================================================================

def print_invoice_details(invoice, tax_doc=None, show_items=True, client_data=None):
    """Print formatted invoice details with enhanced information

    Args:
        invoice: Invoice document
        tax_doc: Tax template document (optional)
        show_items: Whether to show detailed item information (default: True)
        client_data: Client data dict with client_id_number (optional)
    """
    status_emoji = {
        "Draft": "📝",
        "Non Processed": "✅",
        "Tax Calculation Error": "🔺",
        "Processing": "⚙️",
        "Processing Error": "⚠️",
        "Issued": "📄",
        "Rejected": "❌",
        "Contingency": "🚨",
        "Unused": "🗑️",
    }

    emoji = status_emoji.get(invoice.invoice_status, "✓")
    print(
        f"\n{emoji} {invoice.invoice_status} invoice created successfully: {invoice.name}"
    )

    # Client information
    print(f"  Client: {invoice.client_name}")
    if client_data and "client_id_number" in client_data:
        print(f"  {invoice.client_type}: {client_data['client_id_number']}")
    elif invoice.client_type:
        client_label = "CNPJ" if invoice.client_type == "Company" else "CPF"
        if invoice.client_id_number:
            print(f"  {client_label}: {invoice.client_id_number}")

    # Status and workflow fields
    print(f"  Status: {invoice.invoice_status}")
    if invoice.invoice_id:
        print(f"  Invoice ID: {invoice.invoice_id}")

    # Issued invoice fields
    if invoice.invoice_status == "Issued":
        if invoice.invoice_serie:
            print(f"  Invoice Serie: {invoice.invoice_serie}")
        if invoice.invoice_number:
            print(f"  Invoice Number: {invoice.invoice_number}")
        if invoice.invoice_ref_series:
            print(f"  Invoice Ref. Series: {invoice.invoice_ref_series}")
        if invoice.is_return_invoice:
            print("  Return Invoice: Enabled ✓")
        if invoice.invoice_link:
            print(f"  Invoice Link: {invoice.invoice_link[:50]}...")

    # Product and items information
    if show_items and invoice.invoice_items_table:
        print(
            f"  Items: {len(invoice.invoice_items_table)} (Total: {invoice.product_quantity} units)"
        )
        for idx, item in enumerate(invoice.invoice_items_table, 1):
            print(f"    {idx}. {item.item_name}")
            print(f"       Code: {item.item_code}")
            print(f"       Quantity: {item.quantity}")
            print(f"       Rate: R$ {item.rate:.2f}")
            print(f"       Amount: R$ {item.amount:.2f}")
            if hasattr(item, "serial_number") and item.serial_number:
                print(f"       Serial: {item.serial_number}")
    else:
        item_count = (
            len(invoice.invoice_items_table) if invoice.invoice_items_table else 0
        )
        print(f"  Items: {item_count} (Total: {invoice.product_quantity} units)")

    # Financial totals
    print(f"  Brand: {invoice.product_brand}")
    print(
        f"  Total Product Value: R$ {sum(item.amount for item in invoice.invoice_items_table):.2f}"
    )
    print(f"  Freight: R$ {float(invoice.total_freight or 0):.2f}")
    print(f"  Insurance: R$ {float(invoice.total_insurance or 0):.2f}")
    print(f"  Other Expenses: R$ {float(invoice.other_expenses or 0):.2f}")
    print(f"  Discount: R$ {float(invoice.total_discount or 0):.2f}")
    print(f"  Total: R$ {float(invoice.total or 0):.2f}")

    # Tax totals
    if hasattr(invoice, "total_of_taxes") and invoice.total_of_taxes is not None:
        print(f"  Total of Taxes: R$ {float(invoice.total_of_taxes):.2f}")
    if hasattr(invoice, "total_with_taxes") and invoice.total_with_taxes is not None:
        print(f"  Total + Taxes: R$ {float(invoice.total_with_taxes):.2f}")

    print(f"  Gross Weight: {float(invoice.product_gross_weight or 0)} kg")
    print(f"  Net Weight: {float(invoice.product_net_weight or 0)} kg")

    # Individual tax values
    if (
        hasattr(invoice, "icms_value")
        or hasattr(invoice, "ipi_value")
        or hasattr(invoice, "pis_value")
        or hasattr(invoice, "cofins_value")
    ):
        print("  Individual Tax Values:")
        if hasattr(invoice, "icms_value") and invoice.icms_value is not None:
            print(f"    ICMS: R$ {float(invoice.icms_value):.2f}")
        if hasattr(invoice, "ipi_value") and invoice.ipi_value is not None:
            print(f"    IPI: R$ {float(invoice.ipi_value):.2f}")
        if hasattr(invoice, "pis_value") and invoice.pis_value is not None:
            print(f"    PIS: R$ {float(invoice.pis_value):.2f}")
        if hasattr(invoice, "cofins_value") and invoice.cofins_value is not None:
            print(f"    COFINS: R$ {float(invoice.cofins_value):.2f}")
        if (
            hasattr(invoice, "difal_value")
            and invoice.difal_value is not None
            and invoice.difal_value > 0
        ):
            print(f"    DIFAL: R$ {float(invoice.difal_value):.2f}")

    if tax_doc:
        print("  Tax Details:")
        print(
            f"    ICMS Base: R$ {tax_doc.base_calc_icms if tax_doc.base_calc_icms else 0:.2f}"
        )
        print(f"    ICMS Rate: {tax_doc.icms_rate if tax_doc.icms_rate else 0}%")
        print(
            f"    IPI Base: R$ {tax_doc.ipi_calculation_base if tax_doc.ipi_calculation_base else 0:.2f}"
        )
        print(f"    IPI Rate: {tax_doc.ipi_rate if tax_doc.ipi_rate else 0}%")
