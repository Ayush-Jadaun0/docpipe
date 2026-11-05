"""Fields to extract for each document type.

To add a new document type, add an entry here. No other code changes needed.
Field type is one of: "string", "date", "number".
"""

DOC_TYPES = {
    "invoice": {
        "description": "A commercial invoice or bill issued by a vendor to a customer.",
        "keywords": ["invoice", "gstin", "bill to", "due date", "tax invoice"],
        "fields": {
            "invoice_number": ("string", "The invoice number / invoice no."),
            "invoice_date": ("date", "Date the invoice was issued, copied exactly as written."),
            "due_date": ("date", "Payment due date, copied exactly as written."),
            "vendor_name": ("string", "Name of the company issuing the invoice."),
            "customer_name": ("string", "Name of the customer being billed."),
            "gstin": ("string", "GSTIN of the vendor, if present."),
            "subtotal": ("number", "Amount before tax and before any discount."),
            "discount": ("number", "Total discount amount as a positive number, if the invoice shows one."),
            "tax": ("number", "Total tax amount (GST/VAT)."),
            "total": ("number", "Final amount payable."),
            "currency": ("string", "Currency symbol or code, e.g. INR, USD, Rs."),
        },
    },
    "receipt": {
        "description": "A shop or restaurant receipt.",
        "keywords": ["receipt", "cash", "change", "thank you", "qty"],
        "fields": {
            "company": ("string", "Name of the shop or business."),
            "address": ("string", "Address of the shop."),
            "date": ("date", "Date of purchase, copied exactly as written."),
            "subtotal": ("number", "Amount before tax, if shown."),
            "tax": ("number", "Tax amount, if shown."),
            "total": ("number", "Final total paid."),
        },
    },
    "id_card": {
        "description": "An Indian identity document such as a PAN card or Aadhaar card.",
        "keywords": ["permanent account number", "aadhaar", "income tax department", "uidai"],
        "fields": {
            "full_name": ("string", "Name of the card holder."),
            "father_name": ("string", "Father's name, if present."),
            "date_of_birth": ("date", "Date of birth, copied exactly as written."),
            "gender": ("string", "Gender, if present."),
            "pan_number": ("string", "10-character PAN, if present."),
            "aadhaar_number": ("string", "12-digit Aadhaar number, if present."),
            "address": ("string", "Address, if present."),
        },
    },
    "resume": {
        "description": "A resume / CV of a person.",
        "keywords": ["resume", "curriculum vitae", "education", "skills", "experience", "projects"],
        "fields": {
            "full_name": ("string", "Name of the candidate."),
            "email": ("string", "Email address."),
            "phone": ("string", "Phone number."),
            "linkedin": ("string", "LinkedIn URL, if present."),
            "github": ("string", "GitHub URL, if present."),
            "highest_degree": ("string", "Highest or most recent degree, e.g. B.Tech Computer Science."),
            "college": ("string", "Name of the college or university for that degree."),
            "graduation_year": ("string", "Year of graduation or expected graduation."),
            "skills": ("string", "Skills section copied as written, comma separated."),
            "latest_company": ("string", "Most recent employer or internship company, if any."),
        },
    },
    "other": {
        "description": "Any other document.",
        "keywords": [],
        "fields": {
            "document_title": ("string", "Title or heading of the document."),
            "document_date": ("date", "Main date on the document, copied exactly as written."),
            "issuer": ("string", "Organisation or person that issued the document."),
            "reference_number": ("string", "Any reference / ID number."),
        },
    },
}
