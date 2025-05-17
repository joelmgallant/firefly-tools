# Rules for Interacting with the finance-neo / Bills Calendar

This document outlines the rules and conventions for managing financial events within the `finance-neo` Google Calendar and its associated tracking files.

## 1. Calendar Identification

*   **Primary Calendar:** All bills, recurring payments, and financial due dates are tracked in the Google Calendar named `finance-neo`.
    *   Calendar ID: `1755c3b50e83da3aacb593d8bbc62937cad5d0e13fee28edc38e597c8e7d9f04@group.calendar.google.com`

## 2. Marking Events as Paid

To visually and systematically track paid expenses directly within the calendar:

*   **Prefix Summary:** Prepend the event's summary (title) with a checkmark emoji (✅).
    *   Example: An event titled "$100: Netflix" becomes "✅ $100: Netflix" when paid.
*   **Event Color:** Change the event's color to **green**.
    *   The specific green color used corresponds to **Color ID `10`** in Google Calendar.

## 3. TSV File for Detailed Tracking

A Tab-Separated Values (TSV) file is used for a more detailed, exportable, and analyzable record of financial events.

*   **Naming Convention:** The file is typically named following the pattern `financial_events_YYYY-MM.tsv` (e.g., `financial_events_may_2025.tsv`). A new file is generated for each month.
*   **Columns:** The TSV file must contain the following columns:
    1.  `Date`: The due date of the event (YYYY-MM-DD).
    2.  `Name`: The name or description of the event, matching the calendar entry (excluding the "✅" prefix).
    3.  `Amount`: The monetary value of the event. This can be blank if not applicable (e.g., for a due date reminder without a specific amount).
    4.  `Payment Status`: Should be "Paid" or "Unpaid". This status must align with the calendar event's visual cues (checkmark and color).
    5.  `Category`: A classification for the expense (e.g., Investment, Housing, Loan, Utilities, Entertainment, Personal Transfer, Insurance, Bank Fee, Credit Card, Medical).

## 4. Categorization of Expenses

*   All entries in the TSV file should be assigned a relevant `Category`. This helps in financial analysis and budgeting.

## 5. Handling Exceptions

*   Specific events may have unique handling rules. For instance, an event like "Student Loan Payment" might be intentionally kept as "Unpaid" in the TSV and not marked as paid in the calendar until a specific confirmation or action.
*   Any such exceptions should be clearly communicated if automated updates are requested.

## 6. Synchronization and Consistency

*   **Calendar as Source of Truth (for due dates):** The `finance-neo` calendar is the primary source for upcoming due dates.
*   **TSV for Status and Analysis:** The TSV file provides a structured way to see payment statuses and amounts.
*   **Consistency is Key:** Efforts should be made to keep the calendar's visual cues (checkmarks, colors) and the TSV file's `Payment Status` synchronized. If an event is marked paid in the calendar, the TSV should be updated, and vice-versa.

## 7. Monthly Process

*   **Beginning of Month:**
    1.  List all events from the `finance-neo` calendar for the current month.
    2.  Determine their initial paid/unpaid status (most will be unpaid at the start of the month).
    3.  Create the TSV file for the month (e.g., `financial_events_june_2025.tsv`).
*   **During the Month:**
    1.  As bills are paid, update both the calendar event (add "✅", change color to green ID `10`) and the TSV file (`Payment Status` to "Paid").

These rules are intended to ensure clear, consistent, and accurate tracking of financial obligations.

# Firefly III Integration

This project interfaces with a local installation of Firefly III.

*   **API Documentation:** The official API documentation can be found at https://api-docs.firefly-iii.org/
*   **Search API Documentation:** https://docs.firefly-iii.org/references/firefly-iii/search/
*   Refer to this documentation for any questions regarding Firefly III API endpoints, data structures, or authentication.
*   The `money.py` script queries Firefly III for transactions tagged with "payback" and outputs them to a CSV file named `payback.csv`.
