#!/usr/bin/env python
import time
from datetime import datetime, timedelta

from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import InvalidSessionIdException
from seleniumrequests import Chrome
from timeloop import Timeloop
from twilio.rest import Client
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

import os

tl = Timeloop()

class TescoScraper:

    email = os.environ.get('tesco_email')
    pw = os.environ.get('tesco_password')
    twilio_auth = os.environ.get('twilio_auth')

    locations = {'7268': "Banbridge",
                 '7615': 'Craigavon',
                 '7214': 'Lisburn',
                 '7275': 'Newry'}

    phone_numbers = os.environ.get('phone_numbers').split(",")
    print(email)
    print(phone_numbers)

    login_page = "https://secure.tesco.com/account/en-GB/login"
    delivery_url_with_date_and_slot_group = "https://www.tesco.com/groceries/en-GB/slots/delivery/%s?slotGroup=%s"
    collection_url_with_date = "https://www.tesco.com/groceries/en-GB/slots/collection/%s?locationId=%s&postcode=&slotGroup=4"
    unavail_status = ["Unavailable", "UnAvailable", "UNAvailable"]

    driver = None

    def setupSelenium(self):
        CHROMEDRIVER_PATH = '/app/.chromedriver/bin/chromedriver'

        chrome_options = Options()
        # chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.binary_location = os.environ.get('GOOGLE_CHROME_SHIM')
        chrome_options.add_argument(
            '--user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.92 Safari/537.36"')

        self.driver = Chrome(executable_path=CHROMEDRIVER_PATH, options=chrome_options)

    def sendEmail(self, location: str, date):
        send_grid_key = os.environ.get('send_grid')

        message = Mail(
            from_email='tesco-notifier@example.com',
            to_emails='boarder.kite@gmail.com',
            subject=f'Tesco Delivery slot available {location} at {date}',
            html_content=f'<strong>Avail in {location} at {date}</strong>')
        try:
            sg = SendGridAPIClient(send_grid_key)
            response = sg.send(message)
            print(response.status_code)
            print(response.body)
            print(response.headers)
        except Exception as e:
            print(e)


    def sendTextMessage(self, collectionOrDelivery, location, date, button_details):

        account_sid = os.environ.get('twilio_id')
        client = Client(account_sid, self.twilio_auth)

        text_message = collectionOrDelivery + "Tesco Slot Available @ " + location + " at date " + button_details
        print(collectionOrDelivery + text_message + str(datetime.now()))

        for number in self.phone_numbers:
            message = client.messages \
                .create(
                body=text_message,
                from_='+13103214290',
                to=number
            )
        print("Sent notification message " + text_message)
        exit(1)

    def is_logged_id(self):
        self.driver.get(self.login_page)
        try:
            slot_message = WebDriverWait(self.driver, 10).until(
                lambda driver: self.driver.find_element_by_id("username"))
            return False
        except:
            return True

    def loginToTesco(self):
        self.driver.get(self.login_page)
        username = self.driver.find_element_by_id("username")
        username.clear()
        username.send_keys(self.email)

        password = self.driver.find_element_by_id("password")
        password.clear()
        password.send_keys(self.pw)

        buttons = WebDriverWait(self.driver, 10).until(
            lambda driver: driver.find_elements_by_class_name("ui-component__button"))

        for b in buttons:
            b.click()
            time.sleep(1)

        time.sleep(5)
        print("Login Complete")

    def scanForSlots(self):
        print("scanning " + str(datetime.now()))

        today = (datetime.now()).strftime('%Y-%m-%d')
        next_week = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        fortnite = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')

        self.driver.get("https://www.tesco.com/groceries/en-GB/slots/collection")

        for start_date in [today, next_week, fortnite]:
            # Scan 3 week window
            for tesco_location in self.locations:
                # try to search for collection slots first of all
                grocery_collection_url = self.collection_url_with_date % (start_date, tesco_location)

                try:
                    self.driver.get(grocery_collection_url)
                except Exception as e:
                    print("Exception caught from delivery load")
                    print(e)
                    print("Invalid session not sure why")
                    return

                try:
                    buttons = WebDriverWait(self.driver, 5).until(
                        lambda driver: driver.find_elements_by_class_name("available-slot--button"))
                    buttons[-1].click()
                    button_details = buttons[-1].text
                    self.sendTextMessage(tesco_location, "Collection", start_date, button_details)
                except:
                    var = True
                    # nothing found


            try:
                self.driver.get(self.delivery_url_with_date_and_slot_group % (start_date, 4))
            except Exception as e:
                print("Exception caught from delivery load")
                print(e)
                print("Invalid session not sure why")
                return

            # try to search for delivery slots next
            try:
                buttons = WebDriverWait(self.driver, 5).until(
                    lambda driver: driver.find_elements_by_class_name("available-slot--button"))
                buttons[-1].click()
                button_details = buttons[-1].text
                self.sendTextMessage("Home Delivery", "Delivery", start_date, button_details)
            except:
                var = True

            try:
                self.driver.get(self.delivery_url_with_date_and_slot_group % (start_date, 1))
            except Exception as e:
                print("Exception caught from delivery load at slow group")
                print(e)
                print("Invalid session not sure why")
                return

            # try to search for delivery slots next
            try:
                buttons = WebDriverWait(self.driver, 5).until(
                    lambda driver: driver.find_elements_by_class_name("available-slot--button"))
                buttons[-1].click()
                button_details = buttons[-1].text
                self.sendTextMessage("Home Delivery", "Delivery", start_date, button_details)
            except:
                var = True



if __name__ == '__main__':
    scraper = TescoScraper()
    scraper.setupSelenium()
    scraper.sendEmail("testing email", datetime.now())

    @tl.job(interval=timedelta(minutes=10))
    def run():

        try:
            if not scraper.is_logged_id():
                scraper.loginToTesco()
        except InvalidSessionIdException:
            print("Quiting the driver")
            scraper.driver.quit()
            print("Exception logging in, rebuild the scraper")
            scraper.setupSelenium()
            scraper.loginToTesco()

        scraper.scanForSlots()


    run()
    tl.start(block=True)