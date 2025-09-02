# Mashov Message Sender

A web-based application to send personalized messages to students via the Mashov API, using a CSV file as a source for student data.

## Features

*   **Web Interface:** Easy-to-use web interface with a 3-step process for sending messages.
*   **CSV Upload:** Upload a CSV file with student data.
*   **Column Mapping:** Map CSV columns to the required fields (Student ID).
*   **Rich Text Editor:** Compose messages using a rich text editor.
*   **Dynamic Fields:** Use placeholders from the CSV file to personalize messages.
*   **Real-time Logging:** View the status of the message sending process in real-time.
*   **Row Highlighting:** The application highlights the table rows in real-time, indicating the status of each message (processing, success, or failure).
*   **Dry Run Mode:** Test the message sending process without actually sending any messages.
*   **Email Integration:** Optionally send messages via email as well.
*   **Error Handling:** Failed messages are logged, and a CSV file with the failed rows is generated.

## Requirements

*   Python 3.x
*   pip

## Installation and Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/mashov-message-sender.git
    cd mashov-message-sender
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv .venv
    ```

3.  **Activate the virtual environment:**
    *   **Windows:**
        ```bash
        .venv\Scripts\activate
        ```
    *   **macOS/Linux:**
        ```bash
        source .venv/bin/activate
        ```

4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Create a `.env` file:**
    Create a file named `.env` in the root directory of the project and add the following content:
    ```
    MASHOV_SEMEL=your_mashov_semel
    ```
    Replace `your_mashov_semel` with your school's Mashov symbol.

## Usage

1.  **Run the Flask server:**
    ```bash
    python app.py
    ```

2.  **Open your web browser and navigate to `http://127.0.0.1:5000`**

3.  **Follow the 3-step process:**
    *   **Step 1: Login:** Enter your Mashov username, password, and select the academic year.
    *   **Step 2: Upload CSV and Map Columns:**
        *   Upload a CSV file containing student data.
        *   Map the CSV column that contains the student ID numbers.
    *   **Step 3: Compose and Send:**
        *   Write a subject and a message body. You can use placeholders from the CSV file (e.g., `{first_name}`).
        *   Choose to perform a dry run or send the messages.
        *   Monitor the progress in the log section.

## Project Structure

```
.
├── .env                  # Environment variables
├── app.py                # Main Flask application
├── mashov_api.py         # Mashov API client
├── requirements.txt      # Python dependencies
├── templates
│   └── index_rtl.html    # HTML template for the web interface
└── uploads
└── userlist-sample-nodata.csv # Example CSV file without any data
```
