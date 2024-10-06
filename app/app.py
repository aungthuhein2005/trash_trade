from flask import Flask, request, render_template, redirect, url_for, flash, session
import os
import numpy as np
import cv2
from tensorflow.keras.models import load_model
from flask_mysqldb import MySQL
from utils import predict_image

app = Flask(__name__)

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '1234'
app.config['MYSQL_DB'] = 'waste_detection'

# Set a secret key for session management
app.secret_key = 'your_secret_key'

points_dict = {
    0: 10,  # plastic
    1: 15,  # paper
    2: 20,  # glass
    3: 25,  # metal
    4: 5,   # cardboard
    5: 0    # trash
}

trash_type = {
    0: 'plastic',
    1: 'paper',
    2: 'glass',
    3: 'metal',
    4: 'cardboard',
    5: 'trash',
}

# Initialize MySQL
mysql = MySQL(app)

# Load the trained model
model = load_model('D:/projects/data_train/waste_detection_model.h5')

# Ensure the 'uploads' directory exists
if not os.path.exists('uploads'):
    os.makedirs('uploads')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/gif')
def gif():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM items")
    items = cur.fetchall()  # Fetch all items
    cur.close()
    return render_template('gif.html', items=items)

@app.route('/admin/dashboard')
def admin_dashboard():
    # Ensure the user is logged in as admin
    user_id = session.get('user_id')
    if user_id is None:
        flash("Please log in to access the admin dashboard.", "warning")
        return redirect(url_for('login'))

    # Fetch user details to check if they are an admin
    cur = mysql.connection.cursor()
    cur.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()

    if not user or not user[0]:  # Assuming 'is_admin' is a boolean field (0 or 1)
        flash("You do not have permission to access the admin dashboard.", "danger")
        return redirect(url_for('index'))

    # Fetch data for the dashboard (e.g., total users, total points, items, etc.)
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM items")
    total_items = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM orders")
    total_orders = cur.fetchone()[0] or 0  # Handle case where there are no users

    cur.execute("SELECT MONTHNAME(prediction_date) AS month_name, COUNT(*) AS count FROM waste_detection.predictions GROUP BY YEAR(prediction_date), MONTH(prediction_date), MONTHNAME(prediction_date) ORDER BY MONTH(prediction_date);")
    year_predictions = cur.fetchall()
    cur.execute("""
        SELECT 
            week_num.week_number, 
            COALESCE(order_count.order_count, 0) AS order_count
        FROM 
            (SELECT 1 AS week_number UNION ALL
            SELECT 2 UNION ALL
            SELECT 3 UNION ALL
            SELECT 4 UNION ALL
            SELECT 5) AS week_num
        LEFT JOIN 
            (SELECT 
                CEIL(DAY(created_at) / 7) AS week_number, 
                COUNT(*) AS order_count
            FROM 
                orders
            WHERE 
                MONTH(created_at) = MONTH(CURDATE()) AND  
                YEAR(created_at) = YEAR(CURDATE())        
            GROUP BY 
                week_number) AS order_count
        ON 
            week_num.week_number = order_count.week_number
        ORDER BY 
            week_num.week_number;
        """)
    monthly_order = cur.fetchall()

    cur.close()

    return render_template('dashboard/index.html', total_users=total_users, total_items=total_items, total_orders=total_orders,monthly_order=monthly_order,year_predictions=year_predictions)

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    # Ensure the user is logged in as admin
    admin_id = session.get('user_id')
    if admin_id is None:
        flash("Please log in to access the admin dashboard.", "warning")
        return redirect(url_for('login'))

    # Fetch user details to check if they are an admin
    cur = mysql.connection.cursor()
    cur.execute("SELECT is_admin FROM users WHERE id = %s", (admin_id,))
    admin = cur.fetchone()

    if not admin or not admin[0]:  # Assuming 'is_admin' is a boolean field (0 or 1)
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('index'))

    # Delete the user
    try:
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        mysql.connection.commit()
        flash("User deleted successfully.", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash("An error occurred while deleting the user: {}".format(e), "danger")
    finally:
        cur.close()

    return redirect(url_for('admin_users'))

@app.route('/admin/users/ban/<int:user_id>', methods=['POST'])
def ban_user(user_id):
    # Ensure the user is logged in as admin
    admin_id = session.get('user_id')
    if admin_id is None:
        flash("Please log in to access the admin dashboard.", "warning")
        return redirect(url_for('login'))

    # Fetch user details to check if they are an admin
    cur = mysql.connection.cursor()
    cur.execute("SELECT is_admin FROM users WHERE id = %s", (admin_id,))
    admin = cur.fetchone()

    if not admin or not admin[0]:  # Assuming 'is_admin' is a boolean field (0 or 1)
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('index'))

    # Ban the user
    try:
        cur.execute("UPDATE users SET is_banned = TRUE WHERE id = %s", (user_id,))
        mysql.connection.commit()
        flash("User banned successfully.", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash("An error occurred while banning the user: {}".format(e), "danger")
    finally:
        cur.close()

    return redirect(url_for('admin_users'))

@app.route('/admin/orders')
def admin_orders():
    # Ensure the user is logged in as admin
    user_id = session.get('user_id')
    if user_id is None:
        flash("Please log in to access the admin dashboard.", "warning")
        return redirect(url_for('login'))

    # Fetch user details to check if they are an admin
    cur = mysql.connection.cursor()
    cur.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()

    if not user or not user[0]:  # Assuming 'is_admin' is a boolean field (0 or 1)
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('index'))

    # Fetch all orders
    cur.execute("""
        SELECT orders.order_id, orders.name, items.item_name, orders.status, orders.created_at
        FROM orders
        JOIN users ON orders.user_id = users.id
        JOIN items ON orders.item_id = items.id
    """)
    orders = cur.fetchall()
    cur.close()

    return render_template('dashboard/orders.html', orders=orders)

@app.route('/admin/orders/delete/<int:order_id>', methods=['POST'])
def delete_order(order_id):
    # Ensure the user is logged in as admin
    admin_id = session.get('user_id')
    if admin_id is None:
        flash("Please log in to access the admin dashboard.", "warning")
        return redirect(url_for('login'))

    # Fetch user details to check if they are an admin
    cur = mysql.connection.cursor()
    cur.execute("SELECT is_admin FROM users WHERE id = %s", (admin_id,))
    admin = cur.fetchone()

    if not admin or not admin[0]:  # Assuming 'is_admin' is a boolean field (0 or 1)
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('index'))

    # Delete the order
    try:
        cur.execute("DELETE FROM orders WHERE order_id = %s", (order_id,))
        mysql.connection.commit()
        flash("Order deleted successfully.", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash("An error occurred while deleting the order: {}".format(e), "danger")
    finally:
        cur.close()

    return redirect(url_for('admin_orders'))


@app.route('/admin/gifs')
def admin_gifs():
    user_id = session.get('user_id')
    if user_id is None:
        flash("Please log in to access the admin dashboard.", "warning")
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    if not user or not user[0]:  # Assuming 'is_admin' is a boolean field (0 or 1)
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('index'))
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT * from items")
    items = cur.fetchall()
    cur.close()

    return render_template('dashboard/gif.html',gifs=items)

@app.route('/admin/gifs/delete/<int:gif_id>', methods=['POST'])
def delete_gif(gif_id):
    # Ensure the user is logged in as admin
    admin_id = session.get('user_id')
    if admin_id is None:
        flash("Please log in to access the admin dashboard.", "warning")
        return redirect(url_for('login'))

    # Fetch user details to check if they are an admin
    cur = mysql.connection.cursor()
    cur.execute("SELECT is_admin FROM users WHERE id = %s", (admin_id,))
    admin = cur.fetchone()

    if not admin or not admin[0]:  # Assuming 'is_admin' is a boolean field (0 or 1)
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('index'))

    # Delete the order
    try:
        cur.execute("DELETE FROM items WHERE id = %s", (gif_id,))
        mysql.connection.commit()
        flash("Gif deleted successfully.", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash("An error occurred while deleting the gif: {}".format(e), "danger")
    finally:
        cur.close()

    return redirect(url_for('admin_gifs'))


@app.route('/admin/users')
def admin_users():
    # Ensure the user is logged in as admin
    user_id = session.get('user_id')
    if user_id is None:
        flash("Please log in to access the admin dashboard.", "warning")
        return redirect(url_for('login'))

    # Fetch user details to check if they are an admin
    cur = mysql.connection.cursor()
    cur.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()

    if not user or not user[0]:  # Assuming 'is_admin' is a boolean field (0 or 1)
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('index'))

    # Fetch all users
    cur.execute("SELECT id, username, email, points, is_admin, is_banned FROM users")
    users = cur.fetchall()
    cur.close()

    return render_template('dashboard/users.html', users=users)

@app.route('/admin/users/unban/<int:user_id>', methods=['POST'])
def unban_user(user_id):
    # Ensure the user is logged in as admin
    admin_id = session.get('user_id')
    if admin_id is None:
        flash("Please log in to access the admin dashboard.", "warning")
        return redirect(url_for('login'))

    # Fetch user details to check if they are an admin
    cur = mysql.connection.cursor()
    cur.execute("SELECT is_admin FROM users WHERE id = %s", (admin_id,))
    admin = cur.fetchone()

    if not admin or not admin[0]:  # Assuming 'is_admin' is a boolean field (0 or 1)
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('index'))

    # Unban the user
    try:
        cur.execute("UPDATE users SET is_banned = FALSE WHERE id = %s", (user_id,))
        mysql.connection.commit()
        flash("User unbanned successfully.", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash("An error occurred while unbanning the user: {}".format(e), "danger")
    finally:
        cur.close()

    return redirect(url_for('admin_users'))

@app.route('/admin/orders/edit_status/<int:order_id>', methods=['POST'])
def edit_order_status(order_id):
    new_status = request.form.get('status')

    # Ensure the user is logged in as admin
    admin_id = session.get('user_id')
    if admin_id is None:
        flash("Please log in to access the admin dashboard.", "warning")
        return redirect(url_for('login'))

    # Fetch user details to check if they are an admin
    cur = mysql.connection.cursor()
    cur.execute("SELECT is_admin FROM users WHERE id = %s", (admin_id,))
    admin = cur.fetchone()

    if not admin or not admin[0]:  # Assuming 'is_admin' is a boolean field (0 or 1)
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('index'))

    # Update the order status
    try:
        print(new_status)
        cur.execute("UPDATE orders SET status = %s WHERE order_id = %s", (new_status, order_id))
        mysql.connection.commit()
        flash("Order status updated successfully.", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash("An error occurred while updating the order status: {}".format(e), "danger")
    finally:
        cur.close()

    return redirect(url_for('admin_orders'))

@app.route('/admin/items/create', methods=['GET', 'POST'])
def create_item():
    # Ensure the user is logged in as admin
    admin_id = session.get('user_id')
    if admin_id is None:
        flash("Please log in to access the admin dashboard.", "warning")
        return redirect(url_for('login'))

    # Fetch user details to check if they are an admin
    cur = mysql.connection.cursor()
    cur.execute("SELECT is_admin FROM users WHERE id = %s", (admin_id,))
    admin = cur.fetchone()

    if not admin or not admin[0]:  # Assuming 'is_admin' is a boolean field (0 or 1)
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Get item details from the form
        item_name = request.form['item_name']
        item_description = request.form['item_description']
        item_image = request.files['item_image']
        item_value = request.form['item_value']
        item_qty = request.form['item_qty']
        cur = mysql.connection.cursor()
        save_path = os.path.join(app.root_path,'static', 'uploaded_items', item_image.filename)
        item_image.save(save_path)

        try:
            # Insert the new item into the database
            cur.execute(
                "INSERT INTO items (item_name, item_description, item_image, item_value, item_qty) VALUES (%s, %s, %s, %s, %s)",
                (item_name, item_description, item_image, item_value, item_qty)
            )
            mysql.connection.commit()
            flash("Item created successfully.", "success")
        except Exception as e:
            mysql.connection.rollback()
            flash("An error occurred while creating the item: {}".format(e), "danger")
        finally:
            cur.close()

        return redirect(url_for('create_item'))  # Redirect to item list or admin dashboard

    return render_template('dashboard/add-gif.html')  # Render the form template


@app.route('/predict', methods=['POST'])
def predict():
    if 'file' not in request.files:
        return "No file uploaded", 400
    
    file = request.files['file']
    if file.filename == '':
        return "No file selected", 400
    
    # Save the uploaded file to a temporary location
    file_path = os.path.join('uploads', file.filename)
    file.save(file_path)

    try:
        # Make a prediction
        predicted_class = predict_image(file_path, model)

        # Get the corresponding points for the predicted class
        points_awarded = points_dict.get(predicted_class, 0)

        # Update user's points in the database (assuming user ID is 1 for simplicity)
        user_id = session.get('user_id')  # Get the user ID from the session
        if user_id is None:
            flash("Please log in to trade")
            return redirect(url_for('login'))

        cur = mysql.connection.cursor()
        cur.execute("SELECT points FROM users WHERE id = %s", (user_id,))
        current_points = cur.fetchone()[0]

        new_points = current_points + points_awarded
        cur.execute("UPDATE users SET points = %s WHERE id = %s", (new_points, user_id))

        # Insert prediction record into the predictions table
        cur.execute("INSERT INTO predictions (user_id, predicted_class, points_awarded) VALUES (%s, %s, %s)", 
                    (user_id, predicted_class, points_awarded))

        mysql.connection.commit()
        cur.close()

    except Exception as e:
        mysql.connection.rollback()  # Rollback in case of error
        return f"Error during prediction: {str(e)}", 500
    finally:
        # Clean up the uploaded file
        os.remove(file_path)

    return render_template('result.html', predicted_class=trash_type[predicted_class], points_awarded=points_awarded, new_points=new_points)



@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']  # Ideally, hash passwords in a real-world app
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users (username, password, email, points) VALUES (%s, %s, %s)", (username, password, email, 0))
        mysql.connection.commit()
        cur.close()
        flash("Registration successful!", "success")
        return redirect(url_for('index'))
    else:
        return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        # Validate user credentials
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, password, username FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        
        if user and user[1] == password:  
            print (user)
            session['user_id'] = user[0]  
            session['user_name'] = user[2]
            return redirect(url_for('profile'))
        else:
            flash("Invalid credentials", "danger")
    
    return render_template('login.html')

@app.route('/exchange', methods=['POST'])
def exchange():
    # Ensure the user is logged in
    user_id = session.get('user_id')
    if user_id is None:
        flash("Please log in to exchange items.", "warning")
        return redirect(url_for('gif'))
    
    # Retrieve form data
    item_id = request.form['item_id']
    name = request.form['name']
    phone = request.form['phone']
    address = request.form['address']

    # Retrieve item details from the database
    cur = mysql.connection.cursor()
    cur.execute("SELECT item_name, item_value FROM items WHERE id = %s", (item_id,))
    item = cur.fetchone()

    if not item:
        cur.close()
        flash("Item not found.", "danger")
        return redirect(url_for('gif'))

    item_name, item_value = item

    # Retrieve user's current points
    cur.execute("SELECT points FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()

    if not user:
        cur.close()
        flash("User not found.", "danger")
        return redirect(url_for('login'))

    current_points = user[0]

    # Check if user has enough points
    if current_points >= item_value:
        new_points = current_points - item_value

        # Update user's points
        cur.execute("UPDATE users SET points = %s WHERE id = %s", (new_points, user_id))

        # Insert into exchanged_items table
        cur.execute("""
            INSERT INTO exchanged_items (user_id, item_id)
            VALUES (%s, %s)
        """, (user_id, item_id))

        # Insert into order table
        cur.execute("""
            INSERT INTO orders (user_id, item_id, name, phone, address)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, item_id, name, phone, address))

        mysql.connection.commit()
        cur.close()
        flash(f"You have successfully exchanged {item_value} points for {item_name}!", "success")
    else:
        cur.close()
        flash("Not enough points to exchange for this item.", "danger")
    
    return redirect(url_for('gif'))

@app.route('/edit-profile', methods=['GET','POST'])
def editProfile():
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form['username']
        email = request.form['email']
        password = request.form['password']
        cur = mysql.connection.cursor()
        cur.execute("UPDATE users SET username = %s, email = %s, password = %s WHERE id = %s", (name, email, password,user_id))
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        mysql.connection.commit()
        session['user_name'] = name
        cur.close()
        flash("Edit success")
        return render_template('edit-profile.html',user=user)
    else :
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        mysql.connection.commit()
        cur.close()
        return render_template('edit-profile.html',user=user)

@app.route('/admin/edit_order/<int:order_id>', methods=['GET','POST'])
def edit_order(order_id):
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form['item_id']
        user = request.form['user']
        address = request.form['address']
        cur = mysql.connection.cursor()
        cur.execute("UPDATE orders SET item_id = %s, name = %s, address = %s WHERE order_id = %s", (name, user, address,order_id))
        cur.execute("SELECT order_id,item_id,name,address,phone FROM orders WHERE order_id = %s", (order_id,))
        order = cur.fetchone()
        mysql.connection.commit()
        cur.close()
        flash("Edit success")
        return render_template('dashboard/edit-order.html',order=order)
    else :
        cur = mysql.connection.cursor()
        cur.execute("SELECT order_id,item_id,name,address,phone FROM orders WHERE order_id = %s", (order_id,))
        order = cur.fetchone()
        mysql.connection.commit()
        cur.close()
        return render_template('dashboard/edit-order.html',order=order)

@app.route('/admin/edit_gif/<int:gif_id>', methods=['GET','POST'])
def edit_gif(gif_id):
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('login'))
    if request.method == 'POST':
        item_name = request.form['item_name']
        item_description = request.form['item_description']
        item_image = request.files['item_image']
        item_value = request.form['item_value']
        item_qty = request.form['item_qty']
        cur = mysql.connection.cursor()
        save_path = os.path.join(app.root_path,'static', 'uploaded_items', item_image.filename)
        item_image.save(save_path)
        cur.execute("UPDATE items SET item_name = %s, item_description = %s, item_image = %s, item_value = %s, item_qty = %s WHERE id = %s", (item_name, item_description, item_image.filename, item_value, item_qty, gif_id))
        cur.execute("SELECT * FROM items WHERE id = %s", (gif_id,))
        item = cur.fetchone()
        mysql.connection.commit()
        cur.close()
        flash("Edit success")
        return render_template('dashboard/edit-gif.html',item=item)
    else :
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM items WHERE id = %s", (gif_id,))
        item = cur.fetchone()
        mysql.connection.commit()
        cur.close()
        return render_template('dashboard/edit-gif.html',item=item)

@app.route('/profile')
def profile():
    if not session.get('user_id'):
        flash("Please log in to access your profile.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']

    # Retrieve user data
    cur = mysql.connection.cursor()
    cur.execute("SELECT username, points, is_admin FROM users WHERE id = %s", (user_id,))
    user_data = cur.fetchone()

    # Retrieve exchanged items
    cur.execute("""
        SELECT items.item_name, items.item_description, orders.status, items.item_image, exchanged_items.exchanged_date
        FROM exchanged_items
        JOIN items ON exchanged_items.item_id = items.id
        JOIN orders ON orders.user_id = exchanged_items.user_id AND orders.item_id = exchanged_items.item_id
        WHERE exchanged_items.user_id = %s
    """, (user_id,))
    exchanged_items = cur.fetchall()
    cur.close()

    return render_template('profile.html', user=user_data, exchanged_items=exchanged_items)

@app.route('/logout')
def logout():
    session.clear()  # Clear the session
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
