#!/usr/bin/python
import configparser
import re
import os
import click
import smtplib
from _socket import gaierror
from logger import logger
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, UniqueConstraint, LargeBinary, ForeignKey 
from sqlalchemy.ext.declarative.api import declarative_base
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy.orm import relationship

Base = declarative_base()

_session_db = None

def get_session():
    """Return SQLAlchemy session
    """
    global _session_db
    if _session_db is None:
        Session = sessionmaker(bind=engine)
        _session_db = Session()

    return _session_db

class MailMessageHeader(Base):
    __tablename__ = 'MAIL_MESSAGE_SENT_HEADER'
    id = Column('msg_sent_id', String(4000), primary_key = True)
    username = Column(String(100),nullable=True)
    system = Column(String(20),nullable=True)
    msg_sent_to = Column(String(200),nullable=True)
    msg_sent_subject = Column(String(4000),nullable=True)
    msg_sent_prepare = Column(DateTime,nullable=True)
    msg_sent_name = Column(String(200),nullable=True)
    msg_sent_from = Column(String(200),nullable=True)
    msg_sent_date = Column(DateTime,nullable=True)
    msg_sent_cc = Column(String(200),nullable=True)
    msg_sent_body = Column(String(4000), nullable=True)
    msg_sent_bcc = Column(String(200),nullable=True)
    msg_send_idfak = Column(Integer, nullable=True)
    msg_in_reply_to = Column(String(4000), nullable=True)
    msg_id_folder = Column(Integer, nullable=True)
    content_type = Column(String(200),nullable=True)
    
    attachments = relationship('MailMessageSentAttach', backref='attachments')

    def __init__(self,system,msg_sent_subject,msg_sent_date):
        self.system = system
        self.msg_sent_date = msg_sent_date
        self.msg_sent_subject = msg_sent_subject

    @classmethod
    def get_message_header(cls, id):
        """Get message header for given message id
        
        Arguments:
            id {number} -- message id in table MAIL_MESSAGE_HEADER
        """
        session = get_session()
        try:
            message = session.query(cls).get(id)
            print(str(message.msg_sent_subject))
            return message
        except Exception as e:
            logger.error('Error: ' + str(e))

    @classmethod
    def set_date_sent(cls,record):
        session = get_session()
        try:
            record.msg_sent_date = datetime.now()
            session.commit()
        except Exception as e:
            session_pm.rollback()
            logger.exception('MSG: ' + str(e))

class MailMessageSentAttach(Base):
    __tablename__='MAIL_MESSAGE_SENT_ATTACH'
    #id = Column('msg_sent_id', String(4000), primary_key = True)
    msg_sent_id = Column(String(4000),ForeignKey('MAIL_MESSAGE_SENT_HEADER.msg_sent_id'), primary_key=True)
    filename = Column(String(200), nullable=True)
    content_type = Column(String(200),nullable=True)
    body_blob = Column(LargeBinary(), nullable=True)

    #message_header = relationship('MailMessageHeader', backref='MailMessageSentAttach')

    @classmethod
    def get_message_attachment(cls, id):
        session = get_session()
        try:
            message = session.query(cls).get(id)
            return message
        except Exception as e:
            logger.error('Error: ' + str(e))

def initialize_configuration(config_file_path):
    try:
        config_file = configparser.SafeConfigParser(interpolation=configparser.ExtendedInterpolation())
        config_file.read(config_file_path, encoding="UTF-8")
        global config
        config = {
            'out.user': cast(config_file["login credentials"]["mailserver.outgoing.username"], str),
            'out.pw': cast(config_file["login credentials"]["mailserver.outgoing.password"], str),
            'out.host': cast(config_file["mail server settings"]["mailserver.outgoing.smtp.host"], str),
            'out.port': cast(config_file["mail server settings"].get("mailserver.outgoing.smtp.port.tls") or  
                            config_file["mail server settings"].get("mailserver.outgoing.smtp.port.ssl"), str),
            'engine': cast(config_file["db"]["sqlalchemy.engine"], str),
            'out.tls': 'mailserver.outgoing.smtp.port.tls' in config_file["mail server settings"],
            'out.ssl': 'mailserver.outgoing.smtp.port.ssl' in config_file["mail server settings"]
        }
    except KeyError as e:
        logger.error("Error! Key in config file not found.")

def do_connect_to_smpt():
    try:
        if config['out.tls'] and not config['out.ssl']:
            outgoing_mail_server = smtplib.SMTP(config['out.host'], config['out.port'], timeout=5)
            outgoing_mail_server.starttls()
        elif config['out.ssl'] and not config['out.tls']:
            outgoing_mail_server = smtplib.SMTP_SSL(config['out.host'], config['out.port'],timeout=5)
        else:
            logger.error("Found none or two defined protocol in configuration file. Choose one..")
            return None
        (retcode, capabilities) = outgoing_mail_server.login(config['out.user'], config['out.pw'])
        if retcode != 235:
            logger.error("SMTP login failed! Return code: '" + str(retcode) + "'.")
    except gaierror:
        logger.error("SMTP connection failed! Specified host not found.")
    except smtplib.SMTPAuthenticationError as e:
        logger.error("SMTP login failed! Reason: '" + cast(e.smtp_error, str, 'UTF-8') + "'.")
    except Exception as e:
        logger.error("SMTP connection/login failed! Reason: '" + cast(e, str) + "'.")

    return outgoing_mail_server

def sendmail(smtp_connection_server, message_header):
    """Sending email

    message should be in e.g. format:
    
    '''
        From: From Person <from@fromdomain.com>
        To: To Person <to@todomain.com>
        Subject: SMTP e-mail test
    
        This is a test e-mail message.
    '''

    Arguments:
        smtp_connection_server -- An SMTP instance encapsulates an SMTP connection
        message_header -- class of content message header
    """
    REGEXP_CONT_TYPE = re.compile(r"^multipart/")
    if REGEXP_CONT_TYPE.search(message_header.content_type):
        content_type = REGEXP_CONT_TYPE.sub("",message_header.content_type)
    else:
        logger.error("Server MIME types is not properly set. Check Content-Type configuration.")
        return None

    recipients_list = [addr.strip() for addr in re.split(';|,',message_header.msg_sent_to)]

    for to_addrs in recipients_list:
        message = MIMEMultipart(content_type)
        
        message['Subject'] = message_header.msg_sent_subject
        message['To'] = to_addrs
        message['From'] = message_header.msg_sent_from
        message['Reply-to'] = message_header.msg_in_reply_to

        html = """\
        <html>
            <head></head>
            <body>
                <p>Hi!<br>
                <b>This is vindication mail!</b><br>
                You were not paying Taxes. </p>

            </body>
        </html>
        """
        plain = message_header.msg_sent_body

        message.attach(MIMEText(plain,'plain'))
        message.attach(MIMEText(html,'html'))
        
        print("WYSŁANO WIADOMOŚĆ")
        #smtp_connection_server.sendmail(message_header.msg_sent_from, to_addrs, message.as_string())

def close_connection(smtp_connection_server):
    if smtp_connection_server is not None:
        try:
            smtp_connection_server.quit()
        except Exception:
            pass
    

def cast(obj, to_type, options=None):
    try:
        if options is None:
            return to_type(obj)
        else:
            return to_type(obj, options)
    except ValueError and TypeError:
        return obj

@click.command()
@click.option('--conf', default='autoresponder.config.ini', required=True, type=click.Path(exists=True), help='Set path to config file')
def handler(conf):
    initialize_configuration(conf)
    global engine
    engine = create_engine(config['engine'], echo=False)

    msg = MailMessageHeader.get_message_header('116.mga_test2017@outlook.com')
    atach = msg.attachments

    if msg.system == 'SMTP':
        con_server = do_connect_to_smpt()
        if con_server:
            sendmail(con_server, msg)
            MailMessageHeader.set_date_sent(msg)
            close_connection(con_server)


if __name__ == '__main__':
    handler()