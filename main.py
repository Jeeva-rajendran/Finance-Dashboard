import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import plotly.express as px
from io import BytesIO

st.set_page_config(page_title="Simple Finance App" ,page_icon="💰",layout="wide")

category_file = "categories.json"

if "categories" not in st.session_state:
    st.session_state.categories = {
        "Uncategorized" : [],
    }

if os.path.exists(category_file):
    with open(category_file,"r") as f:
        st.session_state.categories = json.load(f)

def save_categories():
    with open(category_file,"w") as f:
        json.dump(st.session_state.categories,f)

def categorize_transaction(df):
    df["Category"] = "Uncategorized"

    for category, keywords in st.session_state.categories.items():
        if category == "Uncategorized" or not keywords:
            continue

        lowered_keywords = [keyword.lower().strip() for keyword in keywords]

        for idx, row in df.iterrows():
            details = row["Details"].lower().strip() 
            if details in lowered_keywords:
                df.at[idx, "Category"] = category
    return df

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Expenses')
    output.seek(0)
    return output

# Function to delete a category
def delete_category(category_to_delete):
    if category_to_delete in st.session_state.categories and category_to_delete != "Uncategorized":
        del st.session_state.categories[category_to_delete]
        save_categories()
        if 'debits_df' in st.session_state and st.session_state.debits_df is not None:
            st.session_state.debits_df = categorize_transaction(st.session_state.debits_df.copy())
        return True
    return False

def load_transaction(file):
    try:
        df = pd.read_csv(file)
        df.columns = [col.strip() for col in df.columns]
        df["Amount"] = df["Amount"].str.replace(",","").astype(float)
        df["Date"] = pd.to_datetime(df["Date"],format="%d-%b-%y")

        
        return categorize_transaction(df)
    
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return None
    
def add_keyword_to_category (category,keyword):
    keyword = keyword.strip()
    if keyword and keyword not in st.session_state.categories[category]:
        st.session_state.categories[category].append(keyword)
        save_categories()
        return True
    
    return False

def main():
    st.title("Finance Dashboard")

    uploaded_file = st.file_uploader("Upload your transaction as CSV file",type=("csv"))

    if uploaded_file is not None:
        df = load_transaction(uploaded_file)

        if df is not None:

            debits_df = df[df["Debit/Credit"] == "Debit"].copy()
            credits_df = df[df["Debit/Credit"] == "Credit"].copy()

            st.session_state.debits_df = debits_df.copy()

            tab1, tab2, tab3, tab4= st.tabs(["Expenses (Debits)", "Payments (Credits)" , "Trends", "Manage Categories"])
            with tab1:          #debits
                new_category = st.text_input("New Category Name")
                add_button = st.button("Add Category")

                if add_button and new_category:
                    if new_category not in st.session_state.categories:
                        st.session_state.categories[new_category] = []
                        save_categories()
                        st.rerun()

                st.subheader("Your Expenses")
                edited_df = st.data_editor(
                    st.session_state.debits_df[["Date","Details","Amount","Category"]],
                    column_config={
                        "Date" : st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                        "Amount" : st.column_config.NumberColumn("Amount", format="%.2f AED"),
                        "Category" : st.column_config.SelectboxColumn(
                            "Category",
                            options = list(st.session_state.categories.keys())
                        )
                    },
                    hide_index = True,
                    use_container_width = True,
                    key = "category_editor"
                )

                save_button = st.button("Apply Changes", type="primary")
                if save_button:
                    for idx, row in edited_df.iterrows():
                        new_category = row["Category"]
                        if new_category == st.session_state.debits_df.at[idx, "Category"]:
                            continue

                        details = row["Details"]
                        st.session_state.debits_df.at[idx, "Category"] = new_category
                        add_keyword_to_category(new_category, details)

                st.subheader("Expense Summary")
                category_totals = st.session_state.debits_df.groupby("Category")["Amount"].sum().reset_index()
                category_totals = category_totals.sort_values("Amount",ascending=False)

                st.dataframe(
                    category_totals,
                    column_config={
                        "Amount" : st.column_config.NumberColumn("Amount", format="%.2f AED")

                    },

                    use_container_width=True,
                    hide_index=True

                    )
                
                fig = px.bar(                       #Add bar graph for better understanding
                    category_totals,
                    x="Category",
                    y="Amount",
                    title="Expenses by Category"
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with tab2:   #Credits
                st.subheader("Payment Summary")
                total_payments = credits_df["Amount"].sum()
                st.metric("Total Payment", f"{total_payments:,.2f} AED")
                st.write(credits_df)
            

            with tab3: # Trends
                st.subheader("Expense Trends Over Time")

                if not st.session_state.debits_df.empty:
                    # Ensure 'Date' is datetime and set as index for resampling
                    trends_df = st.session_state.debits_df.copy()
                    trends_df['Date'] = pd.to_datetime(trends_df['Date']) # Re-ensure datetime type
                    trends_df = trends_df.set_index('Date')

                    # Monthly Total Expenses
                    monthly_total_expenses = trends_df['Amount'].resample('MS').sum().reset_index()
                    monthly_total_expenses.columns = ['Month', 'Total Amount']
                    fig_total_monthly = px.line(
                        monthly_total_expenses,
                        x='Month',
                        y='Total Amount',
                        title='Total Monthly Expenses',
                        markers=True,
                        labels={'Month': 'Month', 'Total Amount': 'Amount (AED)'}
                    )
                    fig_total_monthly.update_xaxes(
                        dtick="M1", # Set x-axis tick to monthly intervals
                        tickformat="%b\n%Y" # Format as "Jan\n2023"
                    )
                    st.plotly_chart(fig_total_monthly, use_container_width=True)

                    st.markdown("---") # Separator

                    # Expenses by Category Over Time (Monthly)
                    st.subheader("Monthly Expenses by Category")
                    category_options = ['All Categories'] + list(st.session_state.categories.keys())
                    selected_category_for_trend = st.selectbox(
                        "Select Category for Trend",
                        category_options
                    )

                    if selected_category_for_trend == 'All Categories':
                        # Group by month and category
                        monthly_category_expenses = trends_df.groupby([pd.Grouper(freq='MS'), 'Category'])['Amount'].sum().reset_index()
                        monthly_category_expenses.columns = ['Month', 'Category', 'Amount']
                        fig_category_monthly = px.line(
                            monthly_category_expenses,
                            x='Month',
                            y='Amount',
                            color='Category',
                            title='Monthly Expenses Across All Categories',
                            markers=True,
                            labels={'Month': 'Month', 'Amount': 'Amount (AED)'}
                        )
                    else:
                        # Filter for selected category
                        filtered_df = trends_df[trends_df['Category'] == selected_category_for_trend]
                        monthly_single_category_expenses = filtered_df.resample('MS')['Amount'].sum().reset_index()
                        monthly_single_category_expenses.columns = ['Month', 'Amount']
                        fig_category_monthly = px.line(
                            monthly_single_category_expenses,
                            x='Month',
                            y='Amount',
                            title=f'Monthly Expenses for {selected_category_for_trend}',
                            markers=True,
                            labels={'Month': 'Month', 'Amount': 'Amount (AED)'}
                        )

                    fig_category_monthly.update_xaxes(
                        dtick="M1",
                        tickformat="%b\n%Y"
                    )
                    st.plotly_chart(fig_category_monthly, use_container_width=True)

                else:
                    st.info("Upload a transaction file to see trends.")

            with tab4: # Manage Categories Tab
                st.subheader("Manage Categories and Keywords")

                # Delete Category Section
                st.markdown("#### Delete Category")
                categories_to_delete_options = [c for c in st.session_state.categories.keys() if c != "Uncategorized"]
                if categories_to_delete_options:
                    category_to_delete = st.selectbox("Select a category to delete:", categories_to_delete_options)
                    if st.button("Delete Selected Category", type="secondary"):
                        if delete_category(category_to_delete):
                            st.success(f"Category '{category_to_delete}' deleted! Transactions re-categorized to 'Uncategorized'.")
                            st.rerun()
                        else:
                            st.error("Could not delete category.")
                else:
                    st.info("No categories available for deletion (excluding 'Uncategorized').")

                st.markdown("---")
                # View/Edit Keywords Section
                st.markdown("#### View/Edit Keywords for Categories")
                selected_category_for_keywords = st.selectbox(
                    "Select a category to view/edit keywords:",
                    list(st.session_state.categories.keys()),
                    key="keyword_category_select"
                )

                if selected_category_for_keywords:
                    current_keywords = st.session_state.categories[selected_category_for_keywords]
                    st.write(f"Current keywords for '{selected_category_for_keywords}': {', '.join(current_keywords) if current_keywords else 'None'}")

                    new_keyword = st.text_input(f"Add new keyword for '{selected_category_for_keywords}':")
                    if st.button(f"Add Keyword to {selected_category_for_keywords}"):
                        if add_keyword_to_category(selected_category_for_keywords, new_keyword):
                            st.success(f"Keyword '{new_keyword}' added to '{selected_category_for_keywords}'.")
                            st.rerun()
                        else:
                            st.warning("Keyword already exists or is empty.")

                    if current_keywords:
                        keyword_to_remove = st.selectbox(
                            f"Select keyword to remove from '{selected_category_for_keywords}':",
                            current_keywords,
                            key="remove_keyword_select"
                        )
                        if st.button(f"Remove Keyword from {selected_category_for_keywords}"):
                            st.session_state.categories[selected_category_for_keywords].remove(keyword_to_remove)
                            save_categories()
                            st.success(f"Keyword '{keyword_to_remove}' removed from '{selected_category_for_keywords}'.")
                            st.rerun()

            # Download button for the full (potentially filtered) categorized data
            excel_data = to_excel(df) # Export the currently filtered data

            st.download_button(
                label="Download Current Data as Excel",
                data=excel_data,
                file_name="categorized_transactions.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("Please upload a valid CSV file to get started.")
    else:
        st.info("Upload your transaction CSV file to begin analyzing your finances!")
            
main()              # To run => streamlit run filename.py