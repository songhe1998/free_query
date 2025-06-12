import json
import os
import random
from typing import List, Dict, Any
from openai import OpenAI

# -------------------------
# File paths and settings
# -------------------------
OUTPUT_PATH = "synthetic_clauses.jsonl"
CLAUSE_LIMIT = 50  # Increased for better coverage

# Initialize OpenAI client
oai_client = OpenAI(api_key="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")

# Define hierarchical fields structure
FIELD_HIERARCHY = {
    "company": {
        "type": "text",
        "subfields": {
            "company_size": {
                "type": "text",
                "values": ["small", "medium", "large", "enterprise"]
            },
            "company_industry": {
                "type": "text",
                "values": ["technology", "finance", "healthcare", "manufacturing", "retail"]
            }
        }
    },
    "financial": {
        "type": "category",
        "subfields": {
            "amount": {
                "type": "numeric",
                "subfields": {
                    "base_amount": {"type": "numeric"},
                    "currency": {"type": "text", "values": ["USD", "EUR", "GBP", "JPY"]},
                    "payment_frequency": {"type": "text", "values": ["monthly", "quarterly", "annually"]}
                }
            },
            "fee": {
                "type": "numeric",
                "subfields": {
                    "termination_fee": {"type": "numeric"},
                    "late_payment_fee": {"type": "numeric"},
                    "fee_type": {"type": "text", "values": ["fixed", "percentage"]}
                }
            }
        }
    },
    "temporal": {
        "type": "category",
        "subfields": {
            "effective_date": {"type": "date"},
            "expiration_date": {"type": "date"},
            "duration": {
                "type": "numeric",
                "subfields": {
                    "term_length": {"type": "numeric"},
                    "term_unit": {"type": "text", "values": ["days", "months", "years"]}
                }
            }
        }
    },
    "risk": {
        "type": "category",
        "subfields": {
            "risk_score": {"type": "numeric"},
            "risk_level": {"type": "text", "values": ["low", "medium", "high"]},
            "risk_factors": {
                "type": "text",
                "values": ["market", "operational", "financial", "legal"]
            }
        }
    }
}

def get_all_fields(hierarchy: Dict) -> List[str]:
    """Recursively get all field names from the hierarchy."""
    fields = []
    for field, details in hierarchy.items():
        fields.append(field)
        if "subfields" in details:
            fields.extend(get_all_fields(details["subfields"]))
    return fields

def generate_synthetic_clause(fields: List[str]) -> str:
    """Generate a synthetic clause with specified fields."""
    try:
        prompt = f"""
        Generate a realistic legal contract clause that includes information about: {', '.join(fields)}
        
        Rules:
        1. Make the clause sound natural and professional
        2. Include specific values for each field
        3. Ensure the clause is grammatically correct and complete
        4. Make the values realistic and consistent
        5. Include the field values in a natural way within the clause text
        
        Return only the clause text.
        """
        
        response = oai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a legal contract clause generation agent."},
                {"role": "user", "content": prompt}
            ]
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"[Error] Failed to generate clause: {e}")
        return f"Standard clause with {', '.join(fields)}."

def synthesize_clauses():
    """Main function to synthesize clauses with hierarchical fields."""
    print("\nSynthesizing clauses with hierarchical fields...")
    
    # Get all fields from hierarchy
    all_fields = get_all_fields(FIELD_HIERARCHY)
    print(f"\nFields to be synthesized: {', '.join(all_fields)}")
    
    # Generate clauses with all fields
    clauses = []
    for _ in range(CLAUSE_LIMIT):
        # Randomly select 3-5 fields for each clause
        num_fields = random.randint(3, 5)
        selected_fields = random.sample(all_fields, num_fields)
        clause = generate_synthetic_clause(selected_fields)
        clauses.append(clause)
        print(f"\nGenerated clause: {clause}")
    
    # Save to JSONL file
    print(f"\nSaving {len(clauses)} clauses to {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, 'w') as f:
        for clause in clauses:
            json.dump({"provision": clause}, f)
            f.write('\n')
    
    print("\nClause synthesis complete!")

if __name__ == "__main__":
    synthesize_clauses() 