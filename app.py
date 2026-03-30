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

# --- 1. SETUP ---
st.set_page_config(page_title="Product Catalog Pro", layout="wide")

# Custom CSS for "Card" look
st.markdown("""
    <style>
    .product-card {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        background-color: white;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

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

# --- 2. STATE MANAGEMENT ---
# This helps us track if a user clicked a specific product to see details
if 'viewing_product' not in st.session_state:
    st.session_state.viewing_product = None

# --- 3. TABS ---
tab1, tab2, tab3 = st.tabs(["🛒 E-Commerce Showcase", "🖼️ Manage Photos", "📂 Bulk Import"])

# --- TAB 1: SHOWCASE (GRID VIEW) ---
with tab1:
    df = pd.read_sql_query("SELECT * FROM products", conn)

    # BACK BUTTON: If viewing a specific product, show a back button
    if st.session_state.viewing_product:
        if st.button("⬅️ Back to Catalog"):
            st.session_state.viewing_product = None
            st.rerun()
            
        # DETAIL VIEW
        prod = df[df['id'] == st.session_state.viewing_product].iloc[0]
        st.divider()
        col_img, col_info = st.columns([1, 1.5])
        with col_img:
            if prod['Image_Path'] and os.path.exists(prod['Image_Path']):
                st.image(prod['Image_Path'], use_container_width=True)
            b_img = generate_barcode_image(prod['Barcode'])
            if b_img: st.image(b_img, caption=f"Barcode: {prod['Barcode']}", width=300)
        with col_info:
            st.title(prod['Product_Name'])
            st.header(f"${prod['Price']:.2f}")
            st.write(f"**Category:** {prod['Category']}")
            st.write(f"**Packing:** {prod['Packing']}")
            st.info(f"**Description:**\n\n{prod['Description']}")
    
    # GRID VIEW
    else:
        st.title("Our Product Range")
        
        # Search & Filter Bar
        s1, s2 = st.columns([2, 1])
        with s1:
            search = st.text_input("🔍 Search products...", placeholder="Enter name or barcode")
        with s2:
            categories = ["All"] + df['Category'].unique().tolist()
            sel_cat = st.selectbox("Filter Category", categories)

        filtered_df = df.copy()
        if search:
            filtered_df = filtered_df[filtered_df['Product_Name'].str.contains(search, case=False) | 
                                     filtered_df['Barcode'].str.contains(search, case=False)]
        if sel_cat != "All":
            filtered_df = filtered_df[filtered_df['Category'] == sel_cat]

        if filtered_df.empty:
            st.warning("No products found.")
        else:
            # CREATE THE GRID (4 columns)
            cols = st.columns(4)
            for index, row in filtered_df.iterrows():
                with cols[index % 4]:
                    # Card Container
                    with st.container(border=True):
                        if row['Image_Path'] and os.path.exists(row['Image_Path']):
                            st.image(row['Image_Path'], use_container_width=True)
                        else:
                            st.image("https://via.placeholder.com/150?text=No+Image", use_container_width=True)
                        
                        st.subheader(row['Product_Name'])
                        st.write(f"**Price: ${row['Price']:.2f}**")
                        st.write(f"📦 {row['Packing']}")
                        
                        # Use button key to track clicks
                        if st.button("View Details", key=f"btn_{row['id']}", use_container_width=True):
                            st.session_state.viewing_product = row['id']
                            st.rerun()

# --- TAB 2 & 3: REMAINS SAME AS PREVIOUS CODE ---
with tab2:
    st.title("Manage Product Photos")
    df_manage = pd.read_sql_query("SELECT id, Product_Name, Barcode FROM products", conn)
    if not df_manage.empty:
        target_product = st.selectbox("Select Product to update photo:", df_manage['Product_Name'].tolist())
        img_file = st.file_uploader("Upload Image", type=['png', 'jpg', 'jpeg'])
        paste_res = paste_image_button("📋 Paste from Clipboard")
        
        final_img = None
        if img_file: final_img = Image.open(img_file)
        elif paste_res.image_data: final_img = paste_res.image_data

        if final_img:
            st.image(final_img, width=250)
            if st.button("Update Photo"):
                fname = f"{uuid.uuid4().hex}.png"
                path = os.path.join(IMAGE_DIR, fname)
                final_img.convert("RGB").save(path)
                c = conn.cursor()
                c.execute("UPDATE products SET Image_Path = ? WHERE Product_Name = ?", (path, target_product))
                conn.commit()
                st.success("Updated!")

with tab3:
    st.title("Excel Bulk Import")
    uploaded_excel = st.file_uploader("Upload Product List (XLSX/CSV)", type=['xlsx', 'csv'])
    if uploaded_excel:
        import_df = pd.read_csv(uploaded_excel) if uploaded_excel.name.endswith('.csv') else pd.read_excel(uploaded_excel)
        st.dataframe(import_df.head())
        if st.button("Confirm Import"):
            for _, r in import_df.iterrows():
                c = conn.cursor()
                c.execute("INSERT INTO products (Product_Name, Category, Price, Barcode, Packing, Description) VALUES (?,?,?,?,?,?)",
                          (r['Product_Name'], r['Category'], r['Price'], str(r['Barcode']), r['Packing'], r['Description']))
            conn.commit()
            st.success("Data Imported!")
