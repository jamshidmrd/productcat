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
st.set_page_config(page_title="Product Showcase", layout="centered")

# Ensure an image directory exists to save uploads
IMAGE_DIR = "product_images"
if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

# Initialize the SQLite Database
def init_db():
    conn = sqlite3.connect('products.db')
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

# Helper function to generate barcode image in memory
def generate_barcode_image(barcode_number):
    try:
        # Code128 is flexible for different lengths and characters
        rv = io.BytesIO()
        barcode.get('code128', str(barcode_number), writer=ImageWriter()).write(rv)
        return rv
    except Exception:
        return None

# --- 2. APPLICATION LAYOUT ---
# Use tabs to separate the showcase from the data entry
tab1, tab2 = st.tabs(["📱 Product Showcase", "➕ Add New Product"])

# --- TAB 1: SHOWCASE TO SUPPLIERS ---
with tab1:
    st.title("Product Catalog")
    
    # Load data from database
    df = pd.read_sql_query("SELECT * FROM products", conn)
    
    if df.empty:
        st.info("Your catalog is empty. Go to the 'Add New Product' tab to get started.")
    else:
        # Filter by category
        categories = ["All"] + df['Category'].unique().tolist()
        selected_category = st.selectbox("Filter by Category", categories)
        
        if selected_category != "All":
            df = df[df['Category'] == selected_category]
            
        # Select a specific product to view
        product_names = df['Product_Name'].tolist()
        selected_product = st.selectbox("Select a Product to View Details", product_names)
        
        if selected_product:
            # Get the specific row for the selected product
            product_data = df[df['Product_Name'] == selected_product].iloc[0]
            
            st.divider()
            
            # Layout: Image on the left, details on the right
            col1, col2 = st.columns([1, 1.5])
            
            with col1:
                # Display Product Image
                image_path = product_data['Image_Path']
                if os.path.exists(image_path):
                    st.image(image_path, use_container_width=True)
                else:
                    st.warning("Image file not found.")
                    
                # Display Generated Barcode
                st.write("**Barcode:**")
                barcode_img = generate_barcode_image(product_data['Barcode'])
                if barcode_img:
                    st.image(barcode_img, width=200)
                else:
                    st.write(product_data['Barcode'])

            with col2:
                # Display Text Details
                st.header(product_data['Product_Name'])
                st.subheader(f"Price: ${product_data['Price']:.2f}")
                st.write(f"**Category:** {product_data['Category']}")
                st.write(f"**Packing Details:** {product_data['Packing']}")
                st.write("**Description:**")
                st.write(product_data['Description'])

# --- TAB 2: DATA ENTRY ---
with tab2:
    st.title("Add a New Product")
    
    # --- Image Upload Section ---
    st.subheader("1. Product Image")
    image_to_save = None
    
    # Option A: Drag and Drop
    uploaded_file = st.file_uploader("Upload an image file (JPG/PNG)", type=['jpg', 'jpeg', 'png'])
    
    st.write("--- OR ---")
    
    # Option B: Clipboard Paste
    paste_result = paste_image_button(
        label="📋 Paste Image from Clipboard",
        background_color="#FF4B4B",
        hover_background_color="#FF6B6B"
    )

    # Determine which image source is being used
    if uploaded_file is not None:
        image_to_save = Image.open(uploaded_file)
        st.image(image_to_save, caption="Preview (From Upload)", width=250)
    elif paste_result.image_data is not None:
        image_to_save = paste_result.image_data
        st.image(image_to_save, caption="Preview (From Clipboard)", width=250)

    # --- Product Details Form ---
    st.subheader("2. Product Details")
    with st.form("new_product_form", clear_on_submit=True):
        name = st.text_input("Product Name*")
        
        # Pre-set categories suitable for your catalog
        category = st.selectbox("Category", ["Coffee Powder", "Coffee Vending Machine", "Accessories", "Other"])
        
        col_price, col_barcode = st.columns(2)
        with col_price:
            price = st.number_input("Price*", min_value=0.0, format="%.2f")
        with col_barcode:
            barcode_num = st.text_input("Barcode Number*")
            
        packing = st.text_input("Packing Details (e.g., 500g pouch, 1 unit/box)")
        description = st.text_area("Product Description")
        
        submitted = st.form_submit_button("Save Product to Database")
        
        if submitted:
            if not name or not barcode_num:
                st.error("Product Name and Barcode are required fields.")
            elif image_to_save is None:
                st.error("Please upload or paste a product image.")
            else:
                # 1. Save the image to the local folder with a unique name
                unique_filename = f"{uuid.uuid4().hex}.png"
                filepath = os.path.join(IMAGE_DIR, unique_filename)
                
                # Convert image to RGB if it has an alpha channel (to save as standard format safely)
                if image_to_save.mode in ("RGBA", "P"):
                    image_to_save = image_to_save.convert("RGB")
                    
                image_to_save.save(filepath)
                
                # 2. Insert into database
                c = conn.cursor()
                c.execute('''
                    INSERT INTO products 
                    (Product_Name, Category, Price, Barcode, Packing, Image_Path, Description)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (name, category, price, barcode_num, packing, filepath, description))
                conn.commit()
                
                st.success(f"✅ Successfully added '{name}' to the catalog!")
