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

DEFAULT_IMAGE = "https://www.freeiconspng.com/thumbs/no-image-icon/no-image-icon-6.png"
IMAGE_DIR = "product_images"

if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

st.markdown("""
    <style>
    .stButton button { width: 100%; border-radius: 5px; }
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

    if st.session_state.viewing_product:
        if st.button("⬅️ Back to All Products"):
            st.session_state.viewing_product = None
            st.rerun()
            
        prod = df[df['id'] == st.session_state.viewing_product].iloc[0]
        st.divider()
        
        col_left, col_right = st.columns([1, 1.5])
        with col_left:
            img_p = prod['Image_Path']
            d_img = img_p if img_p and os.path.exists(img_p) else DEFAULT_IMAGE
            st.image(d_img, use_container_width=True)
            
            b_img = generate_barcode_image(prod['Barcode'])
            if b_img:
                st.image(b_img, width=250)
            else:
                st.code(prod['Barcode'])
                
        with col_right:
            st.title(prod['Product_Name'])
            st.header(f"${prod['Price']:.2f}")
            st.write(f"**Category:** {prod['Category']}")
            st.write(f"**Packing:** {prod['Packing']}")
            st.write("---")
            st.write("**Description:**")
            st.write(prod['Description'] if prod['Description'] else "No description available.")

    else:
        st.title("Product Catalog")
        
        f1, f2 = st.columns([2, 1])
        with f1:
            search_query = st.text_input("🔍 Search...", placeholder="Name or barcode")
        with f2:
            # FIX: Handles empty categories or NaN values during sorting
            if not df.empty:
                cat_list = [str(x) for x in df['Category'].unique() if pd.notna(x)]
                all_cats = ["All"] + sorted(cat_list)
            else:
                all_cats = ["All"]
            
            selected_cat = st.selectbox("Filter Category", all_cats)

        filtered_df = df.copy()
        if search_query:
            filtered_df = filtered_df[
                filtered_df['Product_Name'].str.contains(search_query, case=False) | 
                filtered_df['Barcode'].str.contains(search_query, case=False)
            ]
        if selected_cat != "All":
            filtered_df = filtered_df[filtered_df['Category'] == selected_cat]

        if filtered_df.empty:
            st.info("No products found.")
        else:
            cols = st.columns(4)
            for i, (_, row) in enumerate(filtered_df.iterrows()):
                with cols[i % 4]:
                    with st.container(border=True):
                        img_path = row['Image_Path']
                        card_img = img_path if img_path and os.path.exists(img_path) else DEFAULT_IMAGE
                        st.image(card_img, use_container_width=True)
                        st.markdown(f"**{row['Product_Name']}**")
                        st.write(f"${row['Price']:.2f}")
                        if st.button("View Details", key=f"view_{row['id']}"):
                            st.session_state.viewing_product = row['id']
                            st.rerun()

# --- TAB 2: MANAGE PHOTOS ---
with tab2:
    st.title("Update Product Images")
    all_prods = pd.read_sql_query("SELECT id, Product_Name, Image_Path FROM products", conn)
    
    if all_prods.empty:
        st.warning("Please import products first.")
    else:
        target_name = st.selectbox("Select Product", all_prods['Product_Name'].tolist())
        row_data = all_prods[all_prods['Product_Name'] == target_name].iloc[0]
        
        st.image(row_data['Image_Path'] if row_data['Image_Path'] and os.path.exists(row_data['Image_Path']) else DEFAULT_IMAGE, width=150)
        
        file_up = st.file_uploader("Upload", type=['png', 'jpg', 'jpeg'])
        paste_up = paste_image_button("📋 Paste Image")
        
        final_img = None
        if file_up: final_img = Image.open(file_up)
        elif paste_up.image_data: final_img = paste_up.image_data
            
        if final_img:
            st.image(final_img, width=250)
            if st.button("Save Image"):
                f_name = f"{uuid.uuid4().hex}.png"
                f_path = os.path.join(IMAGE_DIR, f_name)
                if final_img.mode in ("RGBA", "P"): final_img = final_img.convert("RGB")
                final_img.save(f_path)
                c = conn.cursor()
                c.execute("UPDATE products SET Image_Path = ? WHERE id = ?", (f_path, int(row_data['id'])))
                conn.commit()
                st.success("Saved!")
                st.rerun()

# --- TAB 3: BULK IMPORT ---
with tab3:
    st.title("Bulk Import")
    up_file = st.file_uploader("Choose Excel/CSV", type=['xlsx', 'csv'])
    if up_file:
        try:
            import_df = pd.read_csv(up_file) if up_file.name.endswith('.csv') else pd.read_excel(up_file)
            st.dataframe(import_df.head())
            if st.button("Confirm Import"):
                for _, r in import_df.iterrows():
                    try:
                        c = conn.cursor()
                        c.execute('''
                            INSERT INTO products (Product_Name, Category, Price, Barcode, Packing, Description)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (r['Product_Name'], r['Category'], r['Price'], str(r['Barcode']), r['Packing'], r['Description']))
                    except: continue
                conn.commit()
                st.success("Import Complete!")
        except Exception as e:
            st.error(f"Error: {e}")
