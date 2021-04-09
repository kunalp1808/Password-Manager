import concurrent.futures
import gc
import pathlib
import sqlite3
import sys
import time
import traceback
import tracemalloc
from PyQt5 import QtGui, QtWidgets, QtCore
from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal, QRunnable, pyqtSlot, QThreadPool, QObject, QFileInfo
from PyQt5.QtGui import QGuiApplication
from ColorProfile import select_color
from GUI import Ui_MainWindow
from enc_dec import encrypt, decrypt
import qrcode
import pyotp


#QR Code generation....
class Image(qrcode.image.base.BaseImage):
    def __init__(self, border, width, box_size):
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

class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)
    leng = pyqtSignal(int)

#Multithreading implementation
class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        # Add the callback to our kwargs
        self.kwargs['progress_callback'] = self.signals.progress

    @pyqtSlot()
    def run(self):
        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done

#This Runs first...
class MyWork(QtWidgets.QMainWindow):
    def __init__(self):
        super(MyWork, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)      #Calls GUI.py, loads the GUI
        self.show()
        self.threadpool = QThreadPool()
        print("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())
        self.table_dict = None
        self.update_list = 0
        self.num = None
        self.event = None
        self.result = None
        self.counter = 0
        self.val = 1
        self.user_id = None
        self.logged_in = False
        self.show_pass_val = False
        self.ui.setupUi(self)

        self.ui.acnLogout.triggered.connect(self.btn_logout_clk)
        self.ui.acnExit.triggered.connect(self.close)
        self.ui.acnDark.triggered.connect(self.dark)
        self.ui.acnDefault.triggered.connect(self.default)

        # CheckBox actions
        self.ui.tab_login.currentChanged.connect(self.onChange)
        #Show Pass Lbl
        self.ui.lbl_showpass1_signup.mouseReleaseEvent = lambda event: self.show_pass(0)
        self.ui.lbl_showpass2_signup.mouseReleaseEvent = lambda event: self.show_pass(1)
        self.ui.lbl_showpass_add.mouseReleaseEvent = lambda event: self.show_pass(3)
        self.ui.lbl_showpass_login.mouseReleaseEvent = lambda event: self.show_pass(2)
        self.ui.lbl_showpass_pgen.mouseReleaseEvent = lambda event: self.show_pass(5)

        # Button actons
        args = 1
        self.ui.btn_login.clicked.connect(self.log_btn_clk)
        self.ui.btn_signup.clicked.connect(self.reg_btn_clk)
        self.ui.btn_logout.clicked.connect(self.btn_logout_clk)
        self.ui.btn_save_add.clicked.connect(self.save_btn_clk)
        self.ui.btn_signup_done.clicked.connect(self.signup_done_clk)
        self.ui.btn_submit_login.mouseReleaseEvent = lambda event: self.submit_login_clk(self.totp)

        # CellClicked
        self.ui.table_view.cellDoubleClicked.connect(self.cell_was_clicked)
        self.ui.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.disablebtn(True)

        self.ui.acnRefresh_db.setDisabled(True)
        self.ui.menuAccount.setDisabled(True)
        self.ui.menuImport_CSV.setDisabled(True)
        self.ui.acnExport_CSV.setDisabled(True)
        self.ui.acnCng_masterpass.setDisabled(True)
        self.ui.acnCng_username.setDisabled(True)
        self.ui.acnCsv_Update_Acc.setDisabled(True)
        self.ui.menuImport_Db.setDisabled(True)
        self.ui.acnExport_db.setDisabled(True)


    # Register
    def signup_done_clk(self):
        self.ui.stk_signup.setCurrentIndex(0)
        self.ui.tab_login.setGeometry(QtCore.QRect(0, 0, 265, 195))

    def reg_btn_clk(self):
        username_reg = str(self.ui.tbox_user_signup.text())
        pass_reg = str(self.ui.tbox_pass_signup.text())
        pass_confirm = str(self.ui.tbox_repass_signup.text())
        totp = ""
        no = 1
        if len(username_reg) == 0 or len(pass_reg) == 0 or len(pass_confirm) == 0:
            print("Input Fields Cannot Be Empty!")
            select_color(str("red"), no, self)
            self.ui.lbl_warn_signup.setText("Input Fields Cannot Be Empty!")
        else:
            conn = sqlite3.connect('User.db')
            c = conn.cursor()
            c.execute("SELECT 'User' FROM security WHERE `User` = ? ", (username_reg,))
            result = c.fetchall()
            if result:
                select_color(str("red"), no, self)
                self.ui.lbl_warn_signup.setText("Username Already Exists...")
                print("Username Already Exists Please Select a Different Username")
                self.ui.tbox_user_signup.setText("")
            elif pass_reg == pass_confirm:
                if len(pass_reg) < 8:
                    select_color(str("red"), no, self)
                    self.ui.lbl_warn_signup.setText("Password Must Have Atleast 8 Characters!")
                    print("Password Should Be Atleast 8 Characters Long!")
                else:
                    if self.ui.chkbox_2fa_signup.isChecked() == True:
                        self.ui.stk_signup.setCurrentIndex(1)
                        self.ui.tab_login.setGeometry(QtCore.QRect(0, 0, 265, 331))
                        self.ui.stk_signup.setGeometry(QtCore.QRect(3, 3, 261, 301))
                        totp = self.handle(username_reg, pass_reg, self.ui.lbl_qr_signup)
                    print(username_reg, pass_reg)
                    c = conn.cursor()
                    c.execute('INSERT INTO security(User, Hash, Topt) VALUES(?,?,?)',
                              (username_reg, encrypt(pass_reg, username_reg), totp))
                    conn.commit()
                    select_color(str("green"), no, self)
                    self.ui.lbl_warn_signup.setText("New Account Registerd!")
                    self.ui.listWidget.addItem("New Account Registered!")
                    self.ui.listWidget.scrollToBottom()
                    print("New Account Registerd!")
                    self.ui.tbox_pass_signup.setText("")
                    self.ui.tbox_user_signup.setText("")
                    self.ui.tbox_repass_signup.setText("")
            else:
                print("Passwords Doesnt match Please Retype!")
                select_color(str("red"), no, self)
                self.ui.lbl_warn_signup.setText("Passwords Doesnt match Please Retype!")
                self.ui.tbox_repass_signup.setText("")
            conn.close()
        print("out of loop")


    #Login
    def submit_login_clk(self, can):
        totp = can
        print(totp.now())
        if self.ui.tbox_otp_login.text() == totp.now():
            print("Current OTP:", totp.now())
            print("valid")
            self.ui.stk_user.setCurrentIndex(1)
            print("Logged In..")
            self.ui.acnAdd_2FA.setDisabled(True)
            self.disablebtn(False)
            self.ui.tbox_pass_login.setText("")
            self.ui.tbox_user_login.setText("")
            self.ui.listWidget.addItem("Logged In...")
            self.load()
        else:
            print("wrong")

    def log_btn_clk(self):
        tracemalloc.start()
        username = str(self.ui.tbox_user_login.text())
        pass1 = str(self.ui.tbox_pass_login.text())
        no = 0
        print("USER:-", username, "/ PASS:-", pass1)
        conn = sqlite3.connect('User.db')
        if len(username) == 0 or len(pass1) == 0:
            print("Input Fields Cannot Be Empty!")
            select_color(str("red"), no, self)
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
                            print(can)
                            self.ui.stk_login.setCurrentIndex(1)
                            self.totp = pyotp.TOTP(can)
                        else:
                            select_color(str("green"), no, self)
                            print("Logged In..")
                            item = "Welcome " + username
                            self.ui.listWidget.addItem("Logged In...")
                            self.ui.listWidget.addItem(item)
                            self.ui.listWidget.scrollToBottom()
                            self.ui.tbox_user_login.setText("")
                            self.ui.tbox_pass_login.setText("")
                            self.ui.acnDel_2FA.setDisabled(True)
                            self.disablebtn(False)
                            self.load()
                except Exception as ex:
                    select_color(str("red"), no, self)
                    print("You Entered The Wrong Password!", ex)
                    self.ui.lbl_warn_login.setText("You Entered The Wrong Password!")
            else:
                select_color(str("red"), no, self)
                print("No Such User!")
                self.ui.lbl_warn_login.setText("No such user!")
        gc.collect()
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')
        for stat in top_stats[:10]:
            print(stat)
        print("out for the loop")

    def load(self):
        zu = see()
        worker = Worker(zu.maina, self.user_id, self.main_pass)  # Any other args, kwargs are passed to the run function
        worker.signals.result.connect(self.loads)
        worker.signals.finished.connect(self.thread_complete)
        worker.signals.progress.connect(self.setProgressVal)
        self.threadpool.start(worker)

    def loads(self, result):
        print("adaddwdwd", result)
        self.ui.table_view.setRowCount(0)
        t1 = time.perf_counter()
        for row_no, row_data in enumerate(result):
            print("ROW:-", row_no, "/ DATA:-", row_data)
            self.ui.table_view.setSortingEnabled(False)
            self.ui.table_view.insertRow(row_no)
            for column_no, data in enumerate(row_data):
                self.ui.table_view.setItem(row_no, column_no, QtWidgets.QTableWidgetItem(str(data)))
            self.ui.table_view.setSortingEnabled(True)
        t2 = time.perf_counter()
        print("Time Taken:-", t2 - t1)
        self.ui.stk_user.setCurrentIndex(1)
        return

    def thread_complete(self):
        print("THREAD COMPLETE!")

    def setProgressVal(self, val):
        self.counter += 1
        vals = self.counter * 100 / val
        print(val, self.counter, int(vals),"%")
        self.ui.progressBar.setValue(int(vals))
        if vals == 100:
            ku = see()
            setzero = Worker(ku.time)  # Any other args, kwargs are passed to the run function
            setzero.signals.result.connect(self.setProgressZero)
            self.threadpool.start(setzero)

    def setProgressZero(self):
        self.ui.progressBar.setValue(0)
        self.counter = 0


    # Logout
    def btn_logout_clk(self):
        self.logged_in = False
        self.ui.table_view.setRowCount(0)
        self.ui.stk_user.setCurrentIndex(0)
        self.ui.stk_login.setCurrentIndex(0)
        self.ui.progressBar.setValue(0)
        self.counter = 0
        self.val = 1
        self.ui.listWidget.addItem("Logged Out...")
        self.ui.listWidget.scrollToBottom()
        self.disablebtn(True)



    def handle(self, user, password, label):
        salt = pyotp.random_base32()
        url = pyotp.totp.TOTP(salt).provisioning_uri(user, issuer_name="1PassGo!")
        label.setPixmap(
            qrcode.make(url, image_factory=Image).pixmap())
        # totp = pyotp.TOTP(salt)
        # totp = pyotp.TOTP("VADCBKIX63IN7O4E")
        aa = encrypt(password, salt)
        print(aa)
        # print("Current OTP:", totp.now())
        return aa


    #GUI
    def onChange(self, id):
        if id == 0:
            if self.ui.stk_login.currentIndex() == 1:
                self.ui.tab_login.setGeometry(QtCore.QRect(0, 0, 265, 141))
            else:
                self.ui.tab_login.setGeometry(QtCore.QRect(0, 0, 265, 141))
        else:
            if self.ui.stk_signup.currentIndex() == 1:
                self.ui.tab_login.setGeometry(QtCore.QRect(0, 0, 265, 331))
            else:
                self.ui.tab_login.setGeometry(QtCore.QRect(0, 0, 265, 185))

    def dark(self):
        sshFile = "black.qss"
        with open(sshFile, "r") as fh:
            self.ui.centralwidget.setStyleSheet(fh.read())
        print("done")
        fh.close()
        sshFile = "black_menubar.qss"
        with open(sshFile, "r") as fh:
            self.ui.menubar.setStyleSheet(fh.read())
        print("done")
        fh.close()
        sshFile = "black_tab.qss"
        with open(sshFile, "r") as fh:
            self.ui.tab_login.setStyleSheet(fh.read())
        print("done")
        fh.close()

    def default(self):
        self.ui.centralwidget.setStyleSheet("")
        self.ui.menubar.setStyleSheet("")
        self.ui.tab_login.setStyleSheet("")

    def show_pass(self, event):
        chk = [self.ui.tbox_pass_signup, self.ui.tbox_repass_signup, self.ui.tbox_pass_login, self.ui.tbox_pass_add,
               0, self.ui.tbox_genpass_pgen, self.dlb.tbox_pass]
        if self.show_pass_val is False:
            print(event)
            chk[event].setEchoMode(QtWidgets.QLineEdit.Normal)
            self.show_pass_val = True
        else:
            chk[event].setEchoMode(QtWidgets.QLineEdit.Password)
            self.show_pass_val = False

    def tick_box_login(self, state):
        self.tk_box(state, 0)

    def tick_box_reg(self, state):
        self.tk_box(state, 1)

    def tick_box_add(self, state):
        self.tk_box(state, 2)

    def tick_box_pgen(self, state):
        self.tk_box(state, 4)

    def tk_box(self, state, val):
        chk = [self.ui.tbox_pass_login, self.ui.tbox_pass_signup, self.ui.tbox_pass_add, 0,
               self.ui.tbox_genpass_pgen]
        if state == QtCore.Qt.Checked:
            print("Show Password")
            chk[val].setEchoMode(QtWidgets.QLineEdit.Normal)
            if val == 1:
                self.ui.tbox_repass_signup.setEchoMode(QtWidgets.QLineEdit.Normal)
        else:
            print("Hide Password")
            chk[val].setEchoMode(QtWidgets.QLineEdit.Password)
            if val == 1:
                self.ui.tbox_repass_signup.setEchoMode(QtWidgets.QLineEdit.Password)

    # disable/enable buttons....
    def disablebtn(self, bool):
        if bool is True:
            self.ui.acnLight.setDisabled(True)
        self.ui.btn_logout.setDisabled(bool)
        self.ui.acnLogout.setDisabled(bool)
        self.ui.acnExit.setDisabled(bool)


    #Table
    def cell_was_clicked(self, row, column):
        print("Row %d and Column %d was clicked" % (row, column))
        if column == 1 or column == 2:
            self.copySlot(None, column, row)
        elif column == 2:
            self.copySlot(None, column, row)
        return

    def copySlot(self, event, mode, rowdata):
        print(event)
        if rowdata is None:
            row = self.ui.table_view.rowAt(event.y())
        else:
            row = rowdata
        print(row)
        cell = self.ui.table_view.item(row, 1)
        data = cell.data(Qt.DisplayRole)
        print(data)
        if mode == 2:
            cell = self.ui.table_view.item(row, 0)
            acc_name = cell.data(Qt.DisplayRole)
            conn = sqlite3.connect('Accounts.db')
            conn.commit()
            c = conn.cursor()
            c.execute("SELECT Hash FROM accounts WHERE `Account` = ? AND `User` = ?", (acc_name, data))
            result = c.fetchone()
            conn.close()
            for hash in result:
                print("match found:-", hash)
                data = self.decrypt_pass(hash)
            self.ui.listWidget.addItem("Password Copied To Clipboard!")
        else:
            self.ui.listWidget.addItem("Username Copied To Clipboard!")
        self.ui.listWidget.scrollToBottom()
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(data)
        print("copied", data)
        self.ui.listWidget.scrollToBottom()
        return


    def decrypt_pass(self, data):
        main_pass = str(self.main_pass)
        new = decrypt(main_pass, data)
        print("pass = ", new)
        return new


    #Add Accounts
    def save_btn_clk(self):
        acc_name = str(self.ui.tbox_acc_add.text())
        username = str(self.ui.tbox_user_add.text())
        password = str(self.ui.tbox_pass_add.text())
        user_id = self.user_id
        no = 2
        if len(username) == 0 or len(password) == 0 or len(acc_name) == 0:
            print("Input Fields Cannot Be Empty!")
            select_color(str("red"), no, self)
            self.ui.lbl_warn_add.setText("Input Fields Cannot Be Empty!")
        else:
            conn = sqlite3.connect('Accounts.db')
            c = conn.cursor()
            c.execute("SELECT Account, User FROM accounts WHERE `Account` = ? AND `User` = ? AND `security_ID` = ?",
                      (acc_name, username, user_id))
            result = c.fetchall()
            if result:
                for _ in result:
                    select_color(str("red"), no, self)
                    self.ui.lbl_warn_add.setText("Username Already Exists...")
                    print("Username Already Exists, Select a Different Username")
                    self.ui.tbox_user_add.setText("")
                    break
            elif len(password) < 8:
                select_color(str("red"), no, self)
                self.ui.lbl_warn_add.setText("Password Must Have Atleast 8 Characters!")
                print("Password Should Be Atleast 8 Characters Long!")
            else:
                now = QDate.currentDate()
                date = now.toString(Qt.DefaultLocaleShortDate)
                print(acc_name, username, password, str(self.main_pass), date)
                c = conn.cursor()
                c.execute('INSERT INTO accounts(Account, User, Hash, Date, security_ID) VALUES(?,?,?,?,?)'
                          , (acc_name, username, encrypt(str(self.main_pass), password), date, user_id))
                conn.commit()
                select_color(str("green"), no, self)
                self.ui.lbl_warn_add.setText("New Account Registerd!")
                self.ui.listWidget.addItem("New Account Added In DB!")
                self.ui.listWidget.scrollToBottom()
                check = ""
                hid_pass = str("")
                for _ in password:
                    hid_pass += str("●")
                if check == "" or acc_name.find(check) != -1 or username.find(check) != -1 or date.find(
                        check) != -1:
                    new_row = self.ui.table_view.rowCount()
                    print("row count add", new_row)
                    self.ui.table_view.setSortingEnabled(False)
                    self.ui.table_view.insertRow(new_row)
                    temp_list = [acc_name, username, hid_pass, date]
                    for column in range(self.ui.table_view.columnCount()):
                        print("column no:-", column)
                        new_column = temp_list[column]
                        print(new_column)
                        print("column no:-", column)
                        self.ui.table_view.setItem(
                            new_row, column, QtWidgets.QTableWidgetItem(new_column))
                    self.ui.table_view.setSortingEnabled(True)
                if self.table_dict is None and self.update_list == 0:
                    print("list is none")
                    self.backup()
                key = (acc_name, username)
                list1 = [hid_pass, date]
                table_dict = self.table_dict
                table_dict[key] = list1
                print(table_dict)
                self.table_dict = table_dict
            conn.close()
        print("out of loop")


    #Backup
    def backup(self):
        table_dict = {}
        for row in range(self.ui.table_view.rowCount()):
            list1 = []
            for column in range(2, 4):
                item = self.ui.table_view.item(row, column)
                list1.insert(column, item.data(Qt.DisplayRole))
            item = self.ui.table_view.item(row, 0)
            item2 = self.ui.table_view.item(row, 1)
            key = (item.data(Qt.DisplayRole), item2.data(Qt.DisplayRole))
            table_dict[key] = list1
        print("Len:", len(table_dict), table_dict)
        self.table_dict = table_dict


#Login/Multithreading
class see(Ui_MainWindow):
    def leds(self, data):
        hash_len = self.hash_len
        new = decrypt(str(self.m_pass), str(data))
        j = str("")
        for _ in new:
            j += str("●")
        progress = self.progress
        progress.emit(hash_len)
        return j

    def maina(self, user_id, password, progress_callback):
        self.m_pass = password
        conn = sqlite3.connect('Accounts.db')
        print("Main Pass:-", str(self.m_pass))
        c = conn.cursor()
        c.execute("SELECT Account, User, Hash, Date FROM accounts WHERE `security_ID` = ?", (str(user_id),))
        result = c.fetchall()
        conn.close()
        hash_list = []
        start = time.perf_counter()
        for row_data in result:
            hash_list.append(row_data[2])
        self.hash_len = len(hash_list)
        self.progress = progress_callback
        print("adwaddaddawdawdwd", progress_callback)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = executor.map(self.leds, hash_list)
        passes = []
        for f in results:
            passes.append(f)
            print(f)
        table = []
        for row_no, row_data in enumerate(result):
            row = []
            for column_no, data in enumerate(row_data):
                if column_no != 2:
                    row.append(data)
                else:
                    row.append(passes[row_no])
            table.append(row)
        finish = time.perf_counter()
        print(f'Finished in {round(finish - start, 2)} second(s)')
        return table

    def time(self, progress_callback):
        print("here")
        time.sleep(1)


def main():
    app = QtWidgets.QApplication(sys.argv)
    dialog = MyWork()
    app.exec_()

if __name__ == "__main__":
    main()
