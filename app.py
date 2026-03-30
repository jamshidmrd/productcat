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

# --- 1. CONFIGURATION & STYLING ---
st.set_page_config(page_title="Sales Pro Catalog", layout="wide", page_icon="📦")

# Standard placeholder if no image is uploaded
DEFAULT_IMAGE = "https://www.freeiconspng.com/thumbs/no-image-icon/no-image-icon-6.png"
IMAGE_DIR = "product_images"

if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

# Custom CSS for the e-commerce "Card" look
st.markdown("""
    <style>
    .stButton button {
        width: 100%;
        border-radius: 5px;
    }
    .product-card {
        border: 1px solid #e6e9ef;
        border-radius: 10px;
        padding: 10px;
        background-color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABASE LOGIC ---
def init_db():
    conn = sqlite3.connect('products.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Product_Name TEXT,
            Category TEXT,
            Price REAL,
            Barcode TEXT UNIQUE,
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
    except:
        return None

# --- 3. SESSION STATE ---
if 'viewing_product' not in st.session_state:
    st.session_state.viewing_product = None

# --- 4. NAVIGATION TABS ---
tab1, tab2, tab3 = st.tabs(["🛒 Product Showcase", "🖼️ Manage Photos", "📂 Bulk Import (Excel)"])

# --- TAB 1: E-COMMERCE SHOWCASE ---
with tab1:
    df = pd.read_sql_query("SELECT * FROM products", conn)

    # --- DETAIL VIEW ---
    if st.session_state.viewing_product:
        if st.button("⬅️ Back to All Products"):
            st.session_state.viewing_product = None
            st.rerun()
            
        prod = df[df['id'] == st.session_state.viewing_product].iloc[0]
        st.divider()
        
        col_left, col_right = st.columns([1, 1.5])
        with col_left:
            img_path = prod['Image_Path']
            display_img = img_path if img_path and os.path.exists(img_path) else DEFAULT_IMAGE
            st.image(display_img, use_container_width=True)
            
            st.write("**Scannable Barcode:**")
            b_img = generate_barcode_image(prod['Barcode'])
            if b_img:
                st.image(b_img, width=250)
            else:
                st.code(prod['Barcode'])
                
        with col_right:
            st.title(prod['Product_Name'])
            st.subheader(f"Price: ${prod['Price']:.2f}")
            st.write(f"**Category:** {prod['Category']}")
            st.write(f"**Packing:** {prod['Packing']}")
            st.write("---")
            st.write("**Product Description:**")
            st.write(prod['Description'] if prod['Description'] else "No description available.")

    # --- GRID VIEW ---
    else:
        st.title("Product Catalog")
        
        # Filters
        f1, f2 = st.columns([2, 1])
        with f1:
            search_query = st.text_input("🔍 Search by name or barcode", placeholder="Type here...")
        with f2:
            all_cats = ["All"] + sorted(df['Category'].unique().tolist()) if not df.empty else ["All"]
            selected_cat = st.selectbox("Filter Category", all_cats)

        # Filtering Logic
        filtered_df = df.copy()
        if search_query:
            filtered_df = filtered_df[
                filtered_df['Product_Name'].str.contains(search_query, case=False) | 
                filtered_df['Barcode'].str.contains(search_query, case=False)
            ]
        if selected_cat != "All":
            filtered_df = filtered_df[filtered_df['Category'] == selected_cat]

        if filtered_df.empty:
            st.info("No products to show. Please add products via Excel or the manual tab.")
        else:
            # Responsive Grid (4 columns)
            cols = st.columns(4)
            for i, (_, row) in enumerate(filtered_df.iterrows()):
                with cols[i % 4]:
                    with st.container(border=True):
                        # Use default image if path is missing
                        img_p = row['Image_Path']
                        card_img = img_p if img_p and os.path.exists(img_p) else DEFAULT_IMAGE
                        
                        st.image(card_img, use_container_width=True)
                        st.markdown(f"**{row['Product_Name']}**")
                        st.write(f"${row['Price']:.2f}")
                        
                        if st.button("View Details", key=f"view_{row['id']}"):
                            st.session_state.viewing_product = row['id']
                            st.rerun()

# --- TAB 2: MANAGE PHOTOS (UPLOAD / CLIPBOARD) ---
with tab2:
    st.title("Update Product Images")
    all_prods = pd.read_sql_query("SELECT id, Product_Name, Image_Path FROM products", conn)
    
    if all_prods.empty:
        st.warning("No products found in the database. Use Bulk Import first.")
    else:
        selected_target = st.selectbox("Select Product to Edit", all_prods['Product_Name'].tolist())
        current_row = all_prods[all_prods['Product_Name'] == selected_target].iloc[0]
        
        # Show what is currently there
        curr_path = current_row['Image_Path']
        st.write("Current Image:")
        st.image(curr_path if curr_path and os.path.exists(curr_path) else DEFAULT_IMAGE, width=150)
        
        st.divider()
        
        # New Image Inputs
        st.subheader("Upload New Image")
        file_up = st.file_uploader("Drag & Drop File", type=['png', 'jpg', 'jpeg'], key="file_manual")
        st.write("OR")
        paste_up = paste_image_button("📋 Paste Image from Clipboard")
        
        final_file = None
        if file_up:
            final_file = Image.open(file_up)
        elif paste_up.image_data:
            final_file = paste_up.image_data
            
        if final_file:
            st.image(final_file, width=300, caption="Preview of new image")
            if st.button("Confirm and Save Photo"):
                # Save physical file
                new_filename = f"{uuid.uuid4().hex}.png"
                new_path = os.path.join(IMAGE_DIR, new_filename)
                
                if final_file.mode in ("RGBA", "P"):
                    final_file = final_file.convert("RGB")
                final_file.save(new_path)
                
                # Update Database
                c = conn.cursor()
                c.execute("UPDATE products SET Image_Path = ? WHERE id = ?", (new_path, int(current_row['id'])))
                conn.commit()
                st.success(f"Updated photo for {selected_target}!")
                st.rerun()

# --- TAB 3: EXCEL BULK IMPORT ---
with tab3:
    st.title("Import Products via Excel")
    st.write("Upload an Excel file (.xlsx) or CSV with headers: **Product_Name, Category, Price, Barcode, Packing, Description**")
    
    up_file = st.file_uploader("Choose file", type=['xlsx', 'csv'])
    
    if up_file:
        try:
            if up_file.name.endswith('.csv'):
                import_data = pd.read_csv(up_file)
            else:
                import_data = pd.read_excel(up_file)
            
            st.write("Preview:")
            st.dataframe(import_data.head())
            
            if st.button("🚀 Start Bulk Import"):
                count = 0
                for _, row in import_data.iterrows():
                    try:
                        c = conn.cursor()
                        c.execute('''
                            INSERT INTO products (Product_Name, Category, Price, Barcode, Packing, Description)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (row['Product_Name'], row['Category'], row['Price'], 
                              str(row['Barcode']), row['Packing'], row['Description']))
                        count += 1
                    except sqlite3.IntegrityError:
                        # Skip duplicates based on Barcode
                        continue
                conn.commit()
                st.success(f"Successfully imported {count} products!")
        except Exception as e:
            st.error(f"Error reading file: {e}")
