import sqlite3
from enc_dec import encrypt, decrypt
import qrcode
import pyotp
from PyQt5 import QtGui, QtWidgets, QtCore
from GUI import Ui_MainWindow
import sys

class Image(qrcode.image.base.BaseImage):
    def _init_(self, border, width, box_size):
        self.border = border
        self.width = width
        self.box_size = box_size
        print(border, width, box_size)
        size = (width + border * 2) * box_size
        self._image = QtGui.QImage(
            size, size, QtGui.QImage.Format_RGB16)
        self._image.fill(QtCore.Qt.white)

    def pixmap(self):
        return QtGui.QPixmap.fromImage(self._image)

    def drawrect(self, row, col):
        painter = QtGui.QPainter(self._image)
        painter.fillRect(
            (col + self.border) * self.box_size,
            (row + self.border) * self.box_size,
            self.box_size, self.box_size,
            QtCore.Qt.black)

    def save(self, stream, kind=None):
        pass


#This Runs first...
class MyWork(QtWidgets.QMainWindow):
    def __init__(self):
        super(MyWork, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)      #Calls GUI.py, loads the GUI
        self.show()
self.user_id = None
        self.logged_in = False
        self.counter = 0
        self.val = 1

    
        self.ui.btn_login.clicked.connect(self.log_btn_clk)
        self.ui.btn_signup.clicked.connect(self.reg_btn_clk)
        self.ui.btn_logout.clicked.connect(self.btn_logout_clk)

        self.disablebtn(True)

    def reg_btn_clk(self):
        username_reg = str(self.ui.tbox_user_signup.text())
        pass_reg = str(self.ui.tbox_pass_signup.text())
        pass_confirm = str(self.ui.tbox_repass_signup.text())
        totp = ""
        no = 1
        if len(username_reg) == 0 or len(pass_reg) == 0 or len(pass_confirm) == 0:
            print("Input Fields Cannot Be Empty!")
            self.ui.lbl_warn_signup.setText("Input Fields Cannot Be Empty!")
        else:
            conn = sqlite3.connect('User.db')
            c = conn.cursor()
            c.execute("SELECT 'User' FROM security WHERE `User` = ? ", (username_reg,))
            result = c.fetchall()
            if result:
                self.ui.lbl_warn_signup.setText("Username Already Exists...")
                print("Username Already Exists Please Select a Different Username")
                self.ui.tbox_user_signup.setText("")
            elif pass_reg == pass_confirm:
                if len(pass_reg) < 8:
                    self.ui.lbl_warn_signup.setText("Password Must Have Atleast 8 Characters!")
                    print("Password Should Be Atleast 8 Characters Long!")
                else:
                    if self.ui.chkbox_2fa_signup.isChecked() == True:
                        totp = self.handle(username_reg, pass_reg, self.ui.lbl_qr_signup)
                    print(username_reg, pass_reg)
                    c = conn.cursor()
                    c.execute('INSERT INTO security(User, Hash, Topt) VALUES(?,?,?)',
                              (username_reg, encrypt(pass_reg, username_reg), totp))
                    conn.commit()
                    # print(c.lastrowid)
                    self.ui.lbl_warn_signup.setText("New Account Registerd!")
                    self.ui.listWidget.addItem("New Account Registered!")
                    self.ui.listWidget.scrollToBottom()
                    print("New Account Registerd!")
                    self.ui.tbox_pass_signup.setText("")
                    self.ui.tbox_user_signup.setText("")
                    self.ui.tbox_repass_signup.setText("")
            else:
                print("Passwords Doesnt match Please Retype!")
                self.ui.lbl_warn_signup.setText("Passwords Doesnt match Please Retype!")
                self.ui.tbox_repass_signup.setText("")
            conn.close()
        print("out of loop")


    def log_btn_clk(self):
        username = str(self.ui.tbox_user_login.text())
        pass1 = str(self.ui.tbox_pass_login.text())
        no = 0
        print("USER:-", username, "/ PASS:-", pass1)
        conn = sqlite3.connect('User.db')
        if len(username) == 0 or len(pass1) == 0:
            print("Input Fields Cannot Be Empty!")
            self.ui.lbl_warn_login.setText("Input Fields Cannot Be Empty!")
        else:
            c = conn.cursor()
            c.execute("SELECT * FROM security WHERE `User` = ? ", (username,))
            row = c.fetchone()
            conn.close()
            if row:
                print("ID:-", row[0], "/ USER:- ", row[1], "/ HASH:-", row[2], "/ Hash1:-", row[3])
                try:
                    if decrypt(pass1, row[2]) == username:
                        print("dawdawww")
                        self.logged_in = True
                        self.user_id = row[0]
                        self.main_pass = pass1
                        self.username = username
                        if row[3] != "":
                            can = decrypt(pass1, row[3])
                            print(can, "what")
                            self.totp = pyotp.TOTP(can)
                        else:
                            print("Logged In..")
                            item = "Welcome " + username
                            self.ui.listWidget.addItem("Logged In...")
                            self.ui.listWidget.addItem(item)
                            self.ui.listWidget.scrollToBottom()
                            self.ui.tbox_user_login.setText("")
                            self.ui.tbox_pass_login.setText("")
                            self.disablebtn(False)
                            self.load()
                except Exception as ex:
                    print("You Entered The Wrong Password!", ex)
                    self.ui.lbl_warn_login.setText("You Entered The Wrong Password!")
            else:
                print("No Such User!")
                self.ui.lbl_warn_login.setText("No such user!")
        print("out for the loop")

    def handle(self, user, password, label):
        salt = pyotp.random_base32()
        url = pyotp.totp.TOTP(salt).provisioning_uri(user, issuer_name="1PassGo!")
        label.setPixmap(
            qrcode.make(url, image_factory=Image).pixmap())
        aa = encrypt(password, salt)
        print(aa)
        return aa

    def btn_logout_clk(self):
        self.logged_in = False
        self.counter = 0
        self.val = 1
        self.ui.listWidget.addItem("Logged Out...")
        self.ui.listWidget.scrollToBottom()
        self.disablebtn(True)


    def disablebtn(self, bool):
        if bool is not True:
            self.ui.btn_logout.setDisabled(bool)
def main():
    app = QtWidgets.QApplication(sys.argv)
    dialog = MyWork()
    app.exec_()

if __name__ == "__main__":
    main()
