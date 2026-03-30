import streamlit as st
import sqlite3
import pandas as pd
import os
import uuid
import io
from PIL import Image
from streamlit_paste_button import paste_image_button
import barcode
from barcode.writer import ImageWriter

# --- 1. SETUP & INITIALIZATION ---
st.set_page_config(page_title="Sales Pro Catalog", layout="wide")

IMAGE_DIR = "product_images"
if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

def init_db():
    conn = sqlite3.connect('products.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Product_Name TEXT,
            Category TEXT,
            Price REAL,
            Barcode TEXT,
            Packing TEXT,
            Image_Path TEXT,
            Description TEXT
        )
    ''')
    conn.commit()
    return conn

conn = init_db()

def generate_barcode_image(barcode_number):
    try:
        rv = io.BytesIO()
        barcode.get('code128', str(barcode_number), writer=ImageWriter()).write(rv)
        return rv
    except: return None

# --- 2. TABS ---
tab1, tab2, tab3 = st.tabs(["📱 Showcase", "🖼️ Add/Update Photo", "📂 Excel Bulk Import"])

# --- TAB 1: SHOWCASE ---
with tab1:
    st.title("Product Gallery")
    df = pd.read_sql_query("SELECT * FROM products", conn)
    
    if df.empty:
        st.info("Catalog is empty. Import an Excel file or add products manually.")
    else:
        col_search, col_cat = st.columns(2)
        with col_search:
            search = st.text_input("Search Product Name or Barcode")
        with col_cat:
            categories = ["All"] + df['Category'].unique().tolist()
            selected_cat = st.selectbox("Category Filter", categories)

        # Filtering logic
        filtered_df = df.copy()
        if search:
            filtered_df = filtered_df[filtered_df['Product_Name'].str.contains(search, case=False) | 
                                     filtered_df['Barcode'].str.contains(search, case=False)]
        if selected_cat != "All":
            filtered_df = filtered_df[filtered_df['Category'] == selected_cat]

        # Display Grid
        if not filtered_df.empty:
            selected_prod_name = st.selectbox("Click to view details:", filtered_df['Product_Name'].tolist())
            prod = filtered_df[filtered_df['Product_Name'] == selected_prod_name].iloc[0]
            
            st.divider()
            c1, c2 = st.columns([1, 1.5])
            with c1:
                if prod['Image_Path'] and os.path.exists(prod['Image_Path']):
                    st.image(prod['Image_Path'], use_container_width=True)
                else:
                    st.warning("No photo uploaded yet.")
                
                b_img = generate_barcode_image(prod['Barcode'])
                if b_img: st.image(b_img, caption=f"Barcode: {prod['Barcode']}", width=200)
            
            with c2:
                st.header(prod['Product_Name'])
                st.metric("Price", f"${prod['Price']:.2f}")
                st.write(f"**Packing:** {prod['Packing']}")
                st.write(f"**Description:** {prod['Description']}")

# --- TAB 2: ADD/UPDATE PHOTO ---
with tab2:
    st.title("Manage Product Photos")
    df_manage = pd.read_sql_query("SELECT id, Product_Name, Barcode FROM products", conn)
    
    if df_manage.empty:
        st.warning("No products found. Use 'Excel Bulk Import' first.")
    else:
        target_product = st.selectbox("Select Product to add/change photo:", 
                                      df_manage['Product_Name'].tolist())
        
        st.subheader("Upload or Paste Image")
        img_file = st.file_uploader("Drag & Drop Photo", type=['png', 'jpg', 'jpeg'], key="manual_up")
        paste_res = paste_image_button("📋 Paste from Clipboard")
        
        final_img = None
        if img_file: final_img = Image.open(img_file)
        elif paste_res.image_data: final_img = paste_res.image_data

        if final_img:
            st.image(final_img, width=250, caption="Preview")
            if st.button("Save Photo to Product"):
                fname = f"{uuid.uuid4().hex}.png"
                path = os.path.join(IMAGE_DIR, fname)
                if final_img.mode in ("RGBA", "P"): final_img = final_img.convert("RGB")
                final_img.save(path)
                
                c = conn.cursor()
                c.execute("UPDATE products SET Image_Path = ? WHERE Product_Name = ?", (path, target_product))
                conn.commit()
                st.success(f"Photo updated for {target_product}!")

# --- TAB 3: EXCEL BULK IMPORT ---
with tab3:
    st.title("Bulk Import Products")
    st.write("Upload an Excel file with these columns: **Product_Name, Category, Price, Barcode, Packing, Description**")
    
    # Download template button
    template_data = {
        "Product_Name": ["Example Coffee"],
        "Category": ["Coffee Powder"],
        "Price": [15.50],
        "Barcode": ["123456789"],
        "Packing": ["500g Bag"],
        "Description": ["High quality Arabica"]
    }
    st.download_button("Download Excel Template", 
                       pd.DataFrame(template_data).to_csv(index=False), 
                       "template.csv", "text/csv")

    uploaded_excel = st.file_uploader("Choose Excel or CSV file", type=['xlsx', 'csv'])
    
    if uploaded_excel:
        if uploaded_excel.name.endswith('.csv'):
            import_df = pd.read_csv(uploaded_excel)
        else:
            import_df = pd.read_excel(uploaded_excel)
        
        st.write("Preview of data to import:")
        st.dataframe(import_df.head())
        
        if st.button("Confirm Bulk Import"):
            try:
                for _, row in import_df.iterrows():
                    c = conn.cursor()
                    # Check if barcode exists to avoid duplicates
                    c.execute("SELECT id FROM products WHERE Barcode = ?", (str(row['Barcode']),))
                    if not c.fetchone():
                        c.execute('''
                            INSERT INTO products (Product_Name, Category, Price, Barcode, Packing, Description)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (row['Product_Name'], row['Category'], row['Price'], 
                              str(row['Barcode']), row['Packing'], row['Description']))
                conn.commit()
                st.success(f"Imported {len(import_df)} products successfully!")
            except Exception as e:
                st.error(f"Error: Make sure your column names match exactly. {e}")
