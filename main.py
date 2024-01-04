from PySide6.QtWidgets import (QApplication, QLineEdit, QPushButton, QPlainTextEdit, QMainWindow,
                               QListWidget)
from PySide6.QtCore import QObject, QThread, Signal, Qt
from PySide6.QtUiTools import QUiLoader
from PySide6 import QtCore, QtGui
import requests
import random
import string
import time
import os
import ctypes


# Set app icon on taskbar(Delete this 2 lines if you're making a linux build)
myappid = 'isp.tempmail.ol.1'
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

API = 'https://www.1secmail.com/api/v1/'
domain_list = ["1secmail.com", "1secmail.org", "1secmail.net"]
domain = random.choice(domain_list)


# Gets absolute path of resource for builded app
def resource_path(relative_path) -> str:
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return str(os.path.join(base_path, relative_path))


#Used resources
MainWindowRoot = resource_path('Main.ui')
LetterWindowRoot = resource_path('Letter.ui')
Icon = resource_path('icon.ico')


class MailSystem(QObject):
    # Modificated code. Based on https://github.com/pythontoday/temp_email
    adress_signal = Signal(str)
    adress: str = '{test@mail.com}'
    mail_data = Signal(dict)

    is_active: bool = True

    def generate_adress(self) -> None:
        name = string.ascii_lowercase + string.digits
        username = ''.join(random.choice(name) for i in range(10))
        mail = f'{username}@{domain}'

        print(f'[+] Ваш почтовый адрес: {mail}')
        self.is_active = True
        self.adress_signal.emit(mail)

        self.adress = mail

    def check_mail(self, mail: str = '') -> None:
        req_link = f'{API}?action=getMessages&login={mail.split("@")[0]}&domain={mail.split("@")[1]}'
        req_json = requests.get(req_link).json()

        if len(req_json) == 0:
            print('[INFO] На почте пока нет новых сообщений. Проверка происходит автоматически каждые 5 секунд!')
        else:
            id_list = []

            for i in req_json:
                for k, v in i.items():
                    if k == 'id':
                        id_list.append(v)

            print(f'[+] У вас {len(req_json)} входящих! Почта обновляется автоматически каждые 5 секунд!')

            for id in id_list:
                read_msg = f'{API}?action=readMessage&login={mail.split("@")[0]}&domain={mail.split("@")[1]}&id={id}'
                req_json = requests.get(read_msg).json()

                sender = req_json.get('from')
                subject = req_json.get('subject')
                content = req_json.get('textBody')
                msg_id = req_json.get('id')

                letter = {'sender': sender, 'subject': subject, 'content': content, 'id': msg_id}
                self.mail_data.emit(letter)

    def delete_mail(self, mail: str = '') -> None:
        self.is_active = False
        url = 'https://www.1secmail.com/mailbox'

        data = {
            'action': 'deleteMailbox',
            'login': mail.split('@')[0],
            'domain': mail.split('@')[-1]
        }

        req = requests.post(url, data=data)
        print(f'[X] Почтовый адрес {mail} - удален!\n')

    def run(self) -> None:
        self.generate_adress()
        mail_req = requests.get(f'{API}?login={self.adress.split("@")[0]}&domain={self.adress.split("@")[1]}')

        while self.is_active:
            self.check_mail(mail=self.adress)
            time.sleep(5)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        self.root = QUiLoader().load(MainWindowRoot)
        self.root.setWindowIcon(QtGui.QIcon(Icon))

        # Setup Mail
        self.mail_thread = QThread()
        self.mail = MailSystem()
        self.mail.moveToThread(self.mail_thread)

        self.all_letters: dict = {}
        self.letter_id: int = 0

        # Init UI
        self.init_widgets()
        self.init_connections()
        self.mail_thread.start()

        self.root.show()

    def init_widgets(self) -> None:
        self.mail_adress: QLineEdit = self.root.findChild(QLineEdit, "Mail")

        self.save_btn: QPushButton = self.root.findChild(QPushButton, "SaveLatter")
        self.generate_mail_btn: QPushButton = self.root.findChild(QPushButton, "GenerateMail")

        self.letters: QListWidget = self.root.findChild(QListWidget, "Letters")

    def init_connections(self) -> None:
        # Widgets connections
        self.letters.doubleClicked[QtCore.QModelIndex].connect(self.open_letter)
        self.save_btn.clicked.connect(self.save_letter)
        self.generate_mail_btn.clicked.connect(self.generate_mail)

        # Thread connections
        self.mail_thread.started.connect(self.mail.run)
        self.mail.adress_signal.connect(lambda adress: self.mail_adress.setText(adress))
        self.mail.mail_data.connect(self.create_letter)

    def save_letter(self) -> None | int:
        selected_letters = self.letters.selectedIndexes()

        if selected_letters == []:
            return -1

        if not os.path.isdir("saves"):
            os.mkdir("saves")

        for selected_letter in selected_letters:
            with open(f'saves/{self.all_letters[selected_letter.row()]["id"]}', 'w', encoding='utf-8') as letter_save:
                sender = self.all_letters[selected_letter.row()]["sender"]
                subject = self.all_letters[selected_letter.row()]["subject"]
                content = self.all_letters[selected_letter.row()]["content"]

                save_template = f"Отправитель: {sender}\nТема: {subject}\nСодержание: {content}"
                letter_save.write(save_template)

        self.letters.repaint()

    def generate_mail(self) -> None:
        self.mail.delete_mail()
        self.letters.clear()
        self.letters.repaint()
        self.mail.generate_adress()

    def create_letter(self, data: dict) -> None:
        # Creates letter in letters(QListView) and saves it in all_letters
        if self.letters.findItems(f'{data["subject"]} - {data["sender"]}:{data["id"]}',
                                  Qt.MatchExactly) == [] and self.all_letters.get(data["id"]) != data["id"]:
            self.letters.addItem(f'{data["subject"]} - {data["sender"]}:{data["id"]}')
            self.all_letters[self.letter_id] = {"sender": data["sender"],
                                                "subject": data["subject"],
                                                "content": data["content"],
                                                "id": data["id"]}
            self.letter_id += 1

    def open_letter(self, index: int) -> None:
        global letter
        item = index.row()
        letter = Letter(self.all_letters.get(item)["sender"],
                        self.all_letters.get(item)["subject"],
                        self.all_letters.get(item)["content"])


class Letter:
    def __init__(self, author: str, subject: str, content: str) -> None:
        self.root = QUiLoader().load(LetterWindowRoot)
        self.root.setWindowIcon(QtGui.QIcon(Icon))

        # Letter setup
        self.author = author
        self.subject = subject
        self.content = content

        # Setup UI
        self.init_widgets()
        self.root.setWindowTitle(f"Письмо {self.author}:{self.subject}")

        self.root.show()

    def init_widgets(self) -> None:
        self.letter_author: QLineEdit = self.root.findChild(QLineEdit, "Who")
        self.letter_subject: QLineEdit = self.root.findChild(QLineEdit, "Subject")

        self.letter_content: QPlainTextEdit = self.root.findChild(QPlainTextEdit, "LetterContent")

        self.letter_author.setText(self.author)
        self.letter_subject.setText(self.subject)
        self.letter_content.setPlainText(self.content)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec())
