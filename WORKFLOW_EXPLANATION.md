# 🤖 Multi-Agent System Workflow Explanation

## 📋 **Current System Architecture**

Your current app now uses the **full multi-agent system** from `free_query_v3.py`. Here's exactly how the agents work together:

---

## 🔄 **Complete Workflow - Step by Step**

### **Phase 1: System Initialization**
```
🚀 App Startup
    ↓
🔧 OpenAI Configuration Check
    ↓
📊 Database Initialization
    ↓
🧠 Load Existing Schema & Fields
```

### **Phase 2: Query Processing Pipeline**

```
👤 User Input: "What are the termination fees?"
    ↓
🎯 AGENT 1: Query Decision Agent
    ↓
🔍 Classification: "HIT" or "MISS"
    ↓
    ┌─────────────────┬─────────────────┐
    │      HIT        │      MISS       │
    │ (Existing Data) │  (New Field)    │
    └─────────────────┴─────────────────┘
```

---

## 🎯 **Agent Architecture & Responsibilities**

### **🤖 Agent 1: Query Decision Agent**
**Function:** `decide_query_type(query, known_fields)`
**Purpose:** Determines if query needs existing data (HIT) or new extraction (MISS)

```python
# Example Classifications:
"Show me companies" → HIT (company field exists)
"What are termination fees?" → MISS (termination_fee field doesn't exist)
```

### **🔍 Agent 2: New Field Discovery Agent** 
**Function:** `decide_new_field(query, known_fields)`
**Purpose:** Identifies what new field to extract and parent relationships

```python
# Example Output:
Query: "What are termination fees?"
→ new_field: "termination_fee"
→ parent_field: None

Query: "What are the specific penalty amounts?"  
→ new_field: "penalty_amount"
→ parent_field: "amount" (if amount field exists)
```

### **⚡ Agent 3: Field Extraction Agent**
**Function:** `extract_fields_from_clause(clause, fields)`
**Purpose:** Uses LLM to extract specific fields from legal text

```python
# Example:
Clause: "Termination fee shall be $5,000 upon early cancellation"
Fields: ["termination_fee"]
→ Output: {"termination_fee": 5000, "clause": "..."}
```

### **🗄️ Agent 4: SQL Generation Agent**
**Function:** `generate_filter_sql(query, schema, table_name)`
**Purpose:** Converts natural language to SQL queries

```python
# Example:
Query: "Show termination fees greater than $1000"
Schema: {"termination_fee": "REAL", "company": "TEXT"}
→ SQL: "SELECT * FROM clauses WHERE CAST(termination_fee AS REAL) > 1000"
```

### **🔗 Agent 5: Table Merge Agent**
**Function:** `merge_new_fields_to_main_table()`
**Purpose:** Integrates newly extracted fields into main database

### **📊 Agent 6: SQL Execution Agent**
**Function:** `execute_generated_sql(sql_code, db_path)`
**Purpose:** Executes queries and returns formatted results

---

## 🔄 **Complete Workflow Examples**

### **Example 1: HIT Query (Existing Field)**
```
User: "Show me all companies"
    ↓
🎯 Query Decision Agent → "HIT" (company field exists)
    ↓
🗄️ SQL Generation Agent → "SELECT * FROM clauses WHERE company IS NOT NULL"
    ↓
📊 SQL Execution Agent → Returns results
    ↓
📱 Display in Streamlit
```

### **Example 2: MISS Query (New Field Discovery)**
```
User: "What are the termination fees?"
    ↓
🎯 Query Decision Agent → "MISS" (termination_fee doesn't exist)
    ↓
🔍 New Field Discovery Agent → new_field: "termination_fee"
    ↓
📚 Load LEDGAR Clauses (or subset based on parent field)
    ↓
⚡ Field Extraction Agent → Extract "termination_fee" from each clause
    ↓
💾 Store in temporary table "extracted_termination_fee"
    ↓
🔗 Table Merge Agent → Merge into main table
    ↓
🗄️ SQL Generation Agent → Generate query for termination fees
    ↓
📊 SQL Execution Agent → Execute and return results
    ↓
📱 Display in Streamlit with processing log
```

---

## 🧬 **Advanced Features Currently Active**

### **1. 🔗 Parent-Child Field Relationships**
```python
# If "amount" field exists and user asks about "penalty amounts":
parent_field: "amount" 
new_field: "penalty_amount"
# System only processes clauses that already have "amount" values
```

### **2. 📈 Incremental Database Building**
```python
# Database grows dynamically:
Initial: [company]
After Query 1: [company, termination_fee] 
After Query 2: [company, termination_fee, effective_date]
After Query 3: [company, termination_fee, effective_date, liability_limit]
```

### **3. 🧪 Built-in Testing Framework**
```python
# Comprehensive test suite with:
- Database initialization tests
- Field extraction tests  
- Query capability tests
- Field persistence tests
```

### **4. 📊 Real-time Processing Logs**
```python
# User sees live updates:
"[Miss] Query: 'What are termination fees?'. Attempting to extract new field: 'termination_fee'"
"Loading and processing 10 clauses from LEDGAR for field 'termination_fee'"
"Extracting 'termination_fee' from 10 clauses."
"Storing extracted records into new table: 'extracted_termination_fee'"
"Merging new field 'termination_fee' back to main table"
```

---

## 🎛️ **System Controls Available**

### **Sidebar Controls:**
1. **🔄 Rebuild Database** - Reconstruct from LEDGAR corpus
2. **🧪 Run System Tests** - Execute comprehensive test suite  
3. **📊 Database Status** - View current fields and statistics

### **Query Interface:**
1. **🎯 Hit/Miss Classification** - Real-time query type display
2. **🔍 Processing Log** - Live agent activity monitoring
3. **📥 CSV Download** - Export results
4. **🔄 Auto-refresh** - UI updates after new field discovery

---

## 🚀 **Key Advantages of Current System**

### **vs. Simple Query Processor:**
| Feature | Simple System | Current Multi-Agent System |
|---------|---------------|----------------------------|
| **Field Discovery** | ❌ Static fields only | ✅ Dynamic AI-powered discovery |
| **Query Intelligence** | ❌ Basic SQL generation | ✅ Hit/Miss classification |
| **Database Evolution** | ❌ Fixed schema | ✅ Schema grows with queries |
| **Field Relationships** | ❌ Flat structure | ✅ Parent-child hierarchies |
| **Processing Visibility** | ❌ Black box | ✅ Real-time agent logs |
| **Testing** | ❌ No tests | ✅ Comprehensive test suite |

---

## 🔧 **Technical Implementation Details**

### **Agent Communication:**
```python
# Agents pass data through the handle_query() orchestrator:
decision = decide_query_type(query, base_fields)  # Agent 1
if decision == "miss":
    new_field, parent_field = decide_new_field(query, base_fields)  # Agent 2
    records = [extract_fields_from_clause(c, [new_field]) for c in clauses]  # Agent 3
    merge_new_fields_to_main_table(...)  # Agent 5
sql = generate_filter_sql(query, schema, TABLE_NAME)  # Agent 4
execute_generated_sql(sql, SQL_DB_PATH)  # Agent 6
```

### **Data Flow:**
```
LEDGAR Corpus → Field Extraction → Temporary Tables → Main Table → Query Results
```

### **Error Handling:**
- Each agent has fallback mechanisms
- Processing logs show exactly where issues occur
- Graceful degradation if agents fail

---

## 📊 **Current Status**

✅ **All 6 agents are active and working together**
✅ **Full LEDGAR corpus integration** 
✅ **Dynamic field discovery**
✅ **Real-time processing logs**
✅ **Comprehensive testing framework**
✅ **Advanced query intelligence**

Your app now utilizes the **complete multi-agent architecture** with all available functionalities! 