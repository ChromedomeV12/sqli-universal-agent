import subprocess
import os
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from config import PYTHON_BIN, ORACLE_SCRIPT

# Configuration
LOG_FILE = "scan_results.txt"
PAYLOAD_FILE = "payloads.txt"
TUTOR_LOG = "tutor_log.txt"

def run_solver(do_reset=False):
    """Executes the main SQLi solver script."""
    print("[*] Initializing Vulnerability Scan...")
    print("[*] Running 'sqli_final.py' to analyze the environment. Please wait...")
    reset_flag = [] if do_reset else ["--no-reset"]
    try:
        process = subprocess.Popen([PYTHON_BIN, str(ORACLE_SCRIPT)] + reset_flag, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(f"    {line.strip()}")
        process.wait()
        if process.returncode != 0:
            print(f"[!] Warning: Scan finished with return code {process.returncode}")
        else:
            print("[+] Environment analysis complete.")
    except Exception as e:
        print(f"[!] Critical Error running scanner: {e}")
        sys.exit(1)

def load_data():
    """Parses scan_results.txt and payloads.txt into usable dictionaries."""
    results = {}
    payloads = {}
    
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("[+] Less-"):
                    match = re.search(r"Less-(\d+): (.*)", line)
                    if match:
                        lesson_num = match.group(1)
                        results[lesson_num] = match.group(2).strip()
                        
    if os.path.exists(PAYLOAD_FILE):
        with open(PAYLOAD_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            # Split by [Less-X ...] tags
            blocks = re.split(r"\[Less-(\d+) .*?\]", content)
            for i in range(1, len(blocks), 2):
                l_num = blocks[i]
                p_content = blocks[i+1].strip()
                payloads[l_num] = p_content
                
    return results, payloads

def get_vulnerability_explanation(result):
    """Provides technical context based on the detection result."""
    explanation = ""
    if "UNION" in result:
        explanation = (
            "TYPE: UNION-Based SQL Injection\n"
            "The application is vulnerable because it concatenates input directly into a SQL query's WHERE clause. "
            "Using the 'UNION' operator allows combining the results of the original query with a secondary controlled query. "
            "This facilitates data extraction from other tables or database configuration, reflected directly in the application's response."
        )
    elif "Error" in result:
        explanation = (
            "TYPE: Error-Based SQL Injection\n"
            "The application exposes database error messages to the user. This is exploited by injecting functions that "
            "intentionally trigger specific errors (e.g., using 'updatexml()' with an invalid XPath). The database "
            "results are embedded within the resulting error message returned by the server."
        )
    elif "Boolean Blind" in result:
        explanation = (
            "TYPE: Boolean-Based Blind SQL Injection\n"
            "The application does not reflect data or errors but behaves differently based on whether a query returns "
            "true or false. Data is extracted by asking the database binary questions and observing the response "
            "(e.g., presence or absence of specific content), deducing data character by character."
        )
    elif "Time Blind" in result:
        explanation = (
            "TYPE: Time-Based Blind SQL Injection\n"
            "The application provides no visual feedback. Data extraction relies on time-delay functions like SLEEP(). "
            "By instructing the database to pause execution when a condition is met, the attacker can confirm data "
            "attributes by measuring the server's response time."
        )
    elif "Header" in result or "Injection Successful" in result:
        explanation = (
            "TYPE: Header/Cookie-Based Injection\n"
            "The vulnerability exists in the processing of HTTP headers (User-Agent, Referer, or Cookies). If these headers "
            "are used in database queries without sanitization, they serve as injection vectors, often leading to "
            "Second-Order or Blind vulnerabilities."
        )
    else:
        explanation = "TYPE: General SQL Injection. The application lacks proper input sanitization or parameterized queries."

    if "Tamper" in result:
        explanation += "\n\nFILTER BYPASS ALERT: Security filters or WAF detected. Specific encoding or keyword manipulation required."
        
    return explanation

def get_tamper_explanation(tamper_mode):
    """Explains why a specific tamper mode was used."""
    tampers = {
        'waf_bypass': "Non-standard whitespace and double-keyword injection (e.g., 'selselectect') to bypass WAF filtering of common SQL keywords and spaces.",
        'waf_bypass_newline': "URL-encoded newlines and double-keyword injection to bypass filters that block spaces and standard keywords.",
        'space_bypass': "Use of URL-encoded newlines as whitespace delimiters to bypass filters blocking the 'space' character.",
        'keyword_replace': "Keyword doubling (e.g., 'ununionion') to bypass filters that perform a single-pass removal of SQL keywords.",
        'nested': "Deep keyword doubling for both operators (AND/OR) and primary SQL keywords.",
        'inline_comment': "Use of MySQL inline comments (/*!UNION*/) to bypass keyword-based detection while maintaining execution.",
        'comment_strip': "Avoids comment characters (-- - or #) by using logical closure (e.g., AND '1'='1) to balance the query trailing syntax."
    }
    return tampers.get(tamper_mode, "Standard payload structure without specific filter bypass requirements.")

def provide_guidance(lesson_num, result, payload):
    """Generates and logs technical guidance for a specific lesson."""
    output = []
    output.append("="*80)
    output.append(f"SQLI-LABS ANALYSIS REPORT: LESSON {lesson_num}")
    output.append("="*80)
    output.append(f"\n[+] Vulnerability Detected: {result}")
    
    # Extract data if present (e.g. DB: security or dumped credentials)
    data_match = re.search(r"DB: (.*)(?: \||$)", result)
    if data_match:
        output.append(f"\n[*] Extracted Information (Sample/Context):\n    {data_match.group(1)}")
    
    output.append(f"\n[*] Technical Context:")
    explanation = get_vulnerability_explanation(result)
    output.append(explanation)
    
    # Closure Analysis
    closure_match = re.search(r"Closure: (.*?)(?: \||$)", result)
    if closure_match:
        closure = closure_match.group(1).strip()
        output.append(f"\n[*] Query Closure Analysis:")
        output.append(f"    Target closure sequence: {closure if closure else '(None/Integer)'}")
        output.append(f"    Injection must balance the syntax to escape the existing string context.")
        if closure == "'": output.append("    Original Logic: SELECT ... WHERE id='$id'")
        elif closure == '"': output.append('    Original Logic: SELECT ... WHERE id="$id"')
        elif closure == "')": output.append("    Original Logic: SELECT ... WHERE id=('$id')")
        elif closure == '")': output.append('    Original Logic: SELECT ... WHERE id=("$id")')
        elif closure == "))": output.append("    Original Logic: SELECT ... WHERE id=(('$id'))")

    # Tamper Analysis
    tamper_match = re.search(r"Tamper: (.*?)(?: \||$)", result)
    if tamper_match:
        tamper_mode = tamper_match.group(1).strip()
        if tamper_mode != "none":
            output.append(f"\n[*] Filter Bypass Strategy ({tamper_mode}):")
            output.append(f"    {get_tamper_explanation(tamper_mode)}")

    output.append(f"\n[*] Exploitation Strategy:")
    output.append(f"    The following payload is designed for a 'Full Flush'—dumping the 'users' table credentials:")
    output.append(f"\n    PAYLOAD (Browser/HackBar Friendly):\n    {payload}")
    output.append(f"\n    Note: Characters like '&&' or space-placeholders may need URL-encoding (e.g., %26%26 or %a0) depending on the injection point.")
    
    output.append(f"\n[*] Execution Steps:")
    output.append(f"    1. Navigate to the target lesson in the browser.")
    if "POST" in result:
        output.append(f"    2. Submit the payload via POST request (use Burp Suite or HackBar).")
        output.append(f"    3. Analyze the response for the dumped user/password list.")
    elif "Cookie" in result or "Header" in result:
        output.append(f"    2. Modify the relevant HTTP header/Cookie in Burp Suite Repeater.")
        output.append(f"    3. Execute the request and check for credential leakage in the response.")
    else:
        output.append(f"    2. Inject the payload into the URL parameter.")
        output.append(f"    3. Verify the dumped credentials reflected in the page content.")

    full_text = "\n".join(output)
    print(full_text)
    
    with open(TUTOR_LOG, "a", encoding="utf-8") as f:
        f.write(full_text + "\n\n")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="SQLi-Labs Tutor")
    parser.add_argument("--reset", action="store_true", help="Reset the database before scanning")
    args = parser.parse_args()

    with open(TUTOR_LOG, "w", encoding="utf-8") as f:
        f.write("SQLi-Labs Analysis Log\n")
        f.write("Systematic Injection Documentation\n")
        f.write("="*40 + "\n\n")

    run_solver(do_reset=args.reset)
    results, payloads = load_data()
    
    if not results:
        print("[!] No scan results found. Verify scan_results.txt.")
        return

    lessons = sorted(results.keys(), key=int)
    print(f"\n[+] Analysis complete. Identified {len(lessons)} vulnerable lessons.")
    
    while True:
        try:
            choice = input("\nEnter Lesson Number to review (or 'all', 'q' to quit): ").strip()
        except EOFError:
            break
            
        if choice.lower() == 'q':
            print("Exiting. Results logged to tutor_log.txt.")
            break
        elif choice.lower() == 'all':
            print("\nGenerating full documentation...")
            for l_num in lessons:
                provide_guidance(l_num, results[l_num], payloads.get(l_num, "[No Payload Found]"))
            print("\n[+] Full report saved to tutor_log.txt.")
        elif choice in results:
            provide_guidance(choice, results[choice], payloads.get(choice, "[No Payload Found]"))
        else:
            print("[!] Lesson not found in scan results.")

if __name__ == "__main__":
    main()
