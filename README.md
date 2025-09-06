# RSSB Forms & Badge/Token Generator

This project is a multi-functional **Python Flask** web application designed to digitize and streamline various data management processes for organizational events. It replaces paper-based forms with an intuitive web interface, automates data storage, and facilitates the generation of printable assets like **badges** and **tokens**.

---

## Core Functionalities

This application consolidates several key tasks into a single platform:

### 1. SNE (Special Needs & Elderly) Management
- Collect detailed bio-data for senior citizens and individuals with special needs.  
- Manage data for attendants and sewadars.  
- Generate and print custom PDF badges for registered individuals and their attendants.  

### 2. Baal Satsang Token Printing
- Generate various types of printable tokens for children, parents, siblings, and visitors attending Baal Satsang.  

### 3. Blood Camp Donor Registration
- Provide a simple form for individuals to register as blood donors.  
- Allow organizers to view and manage donor status.  

### 4. Mobile Token Generation
- Create printable tokens for mobile phone deposits at events.  

---

## Technology Stack
- **Backend:** Python with Flask Framework  
- **Server:** Gunicorn WSGI Server  
- **Frontend:** HTML, CSS, JavaScript  
- **Database:** SQLite (or other configured database)  
- **PDF Generation:** ReportLab library  

---

## Deployment & Maintenance on EC2

To update the application with the latest changes from the Git repository, follow these steps:

1. SSH into your EC2 instance.  
2. Find the Process ID (PID) of the currently running Gunicorn server using `ps aux | grep gunicorn`.  
3. Stop the Gunicorn server with `kill <PID>`.  
4. Navigate to the project directory `cd rssb_sne_forms`.  
5. Pull the latest code from the repository using `git pull`.  
6. Restart the Gunicorn server:  
   - Run `nohup gunicorn --bind 127.0.0.1:5000 --workers 3 --log-level info "run:app" &`  
   - The `&` keeps it running in the background.  
   - Check `nohup.out` for logs or errors.  

---

✅ Your application is now updated and running with the latest version of the code.
