#    CUPS Cloudprint - Print via Google Cloud Print
#    Copyright (C) 2011 Simon Cadman
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
import cups
import urllib
import logging
import sys
sys.path.insert(0, ".")

from printer import Printer
from printermanager import PrinterManager
from mockrequestor import MockRequestor
from ccputils import Utils

global requestors, printerManagerInstance


def setup_function(function):
    # setup mock requestors
    global requestors
    requestors = []

    # account without special chars
    mockRequestorInstance1 = MockRequestor()
    mockRequestorInstance1.setAccount('testaccount1')
    mockRequestorInstance1.printers = []
    requestors.append(mockRequestorInstance1)

    # with @ symbol
    mockRequestorInstance2 = MockRequestor()
    mockRequestorInstance2.setAccount('testaccount2@gmail.com')
    mockRequestorInstance2.printers = [{'name': 'Save to Google Drive',
                                        'id': '__test_save_docs',
                                        'capabilities': [{'name': 'ns1:Colors',
                                                          'type': 'Feature'}]},
                                       ]
    requestors.append(mockRequestorInstance2)

    # 1 letter
    mockRequestorInstance3 = MockRequestor()
    mockRequestorInstance3.setAccount('t')
    mockRequestorInstance3.printers = []
    requestors.append(mockRequestorInstance3)

    # instantiate printer item
    if function != test_instantiate:
        test_instantiate()


def teardown_function(function):
    global requestors
    requestors = None
    logging.shutdown()
    reload(logging)


def test_parseURI():
    global printerManagerInstance, requestors
    accountName, printerid = printerManagerInstance._getAccountNameAndPrinterIdFromURI(
        Utils.PROTOCOL + "testaccount2%40gmail.com/testid")
    assert printerid == "testid"
    assert accountName == "testaccount2@gmail.com"


def test_parseLegacyURI():
    global printerManagerInstance, requestors

    # 20140210 format
    account, printername, printerid, formatid = printerManagerInstance.parseLegacyURI(
        Utils.OLD_PROTOCOL + "printername/testaccount2%40gmail.com/", requestors)
    assert formatid == printerManagerInstance.URIFormat20140210
    assert account == "testaccount2@gmail.com"
    assert printername == "printername"
    assert printerid is None

    # 20140307 format
    account, printername, printerid, formatid = printerManagerInstance.parseLegacyURI(
        Utils.OLD_PROTOCOL + "printername/testaccount2%40gmail.com/testid", requestors)
    assert formatid == printerManagerInstance.URIFormat20140307
    assert account == "testaccount2@gmail.com"
    assert printername == "printername"
    assert printerid == "testid"

    # 20140308 format
    account, printername, printerid, formatid = printerManagerInstance.parseLegacyURI(
        Utils.OLD_PROTOCOL + "testaccount2%40gmail.com/testid", requestors)
    assert formatid == printerManagerInstance.URIFormat20140308
    assert account == "testaccount2@gmail.com"
    assert printerid == "testid"
    assert printername is None

    # 20140621+ format
    account, printername, printerid, formatid = printerManagerInstance.parseLegacyURI(
        Utils.PROTOCOL + "testaccount2%40gmail.com/testid", requestors)
    assert formatid == printerManagerInstance.URIFormatLatest
    assert account == "testaccount2@gmail.com"
    assert printerid == "testid"
    assert printername is None


def test_getPrinterIDByDetails():
    printerid, requestor = printerManagerInstance.getPrinterIDByDetails(
        "testaccount2@gmail.com", "testid")
    assert printerid == "testid"
    assert isinstance(requestor, MockRequestor)
    assert requestor.getAccount() == 'testaccount2@gmail.com'

    # test fails
    printerid, requestor = printerManagerInstance.getPrinterIDByDetails(
        "accountthatdoesntexist", "testidthatdoesntexist")
    assert printerid is None
    assert requestor is None

    printerid, requestor = printerManagerInstance.getPrinterIDByDetails(
        "testaccount2@gmail.com", None)
    assert printerid is None
    assert requestor is None


def test_getCUPSPrintersForAccount():
    global printerManagerInstance, requestors

    foundprinters = printerManagerInstance.getCUPSPrintersForAccount(
        requestors[0].getAccount())
    assert foundprinters == []

    # total printer
    totalPrinters = 0
    for requestor in requestors:
        totalPrinters += len(requestor.printers)

    fullprintersforaccount = printerManagerInstance.getPrinters(requestors[1].getAccount())
    assert len(fullprintersforaccount) == len(requestors[1].printers)

    fullprinters = printerManagerInstance.getPrinters()
    assert len(fullprinters) == totalPrinters

    printers = printerManagerInstance.getPrinters()
    assert len(printers) == totalPrinters
    printer = printers[0]

    # get ppd
    ppdid = 'MFG:Google;DRV:GCP;CMD:POSTSCRIPT;DES:GoogleCloudPrint;MDL'
    connection = cups.Connection()
    ppds = connection.getPPDs(ppd_device_id=ppdid)
    printerppdname, printerppd = ppds.popitem()

    # test add printer to cups
    assert printerManagerInstance.addPrinter(
        printer['name'],
        printer,
        "test location",
        printerppdname) is not None
    foundprinters = printerManagerInstance.getCUPSPrintersForAccount(
        requestors[1].getAccount())
    # delete test printer
    connection.deletePrinter(printerManagerInstance.sanitizePrinterName(printer['name']))

    assert isinstance(foundprinters, list)
    assert len(foundprinters) == 1
    assert isinstance(connection, cups.Connection)


def test_getPrinter():
    global requestors, printerManagerInstance
    assert printerManagerInstance.getPrinter('test', 'missingaccount') is None
    assert isinstance(printerManagerInstance.getPrinter(
        '__test_save_docs', requestors[1].getAccount()), Printer)
    assert printerManagerInstance.getPrinter('test', requestors[0].getAccount()) is None


def test_instantiate():
    global requestors, printerManagerInstance
    # verify adding single requestor works
    printerManagerInstance = PrinterManager(requestors[0])
    assert printerManagerInstance.requestors[0] == requestors[0]
    assert len(printerManagerInstance.requestors) == 1

    # verify adding whole array of requestors works
    printerManagerInstance = PrinterManager(requestors)
    assert printerManagerInstance.requestors == requestors
    assert len(printerManagerInstance.requestors) == len(requestors)


def test_GetPrinterByURIFails():
    global printerManagerInstance, requestors

    # ensure invalid account returns None/None
    printerIdNoneTest = printerManagerInstance.getPrinterByURI(
        Utils.PROTOCOL + 'testprinter/accountthatdoesntexist')
    assert printerIdNoneTest is None

    # ensure invalid printer on valid account returns None/None
    printerIdNoneTest = printerManagerInstance.getPrinterByURI(
        Utils.PROTOCOL + 'testprinter/' + urllib.quote(requestors[0].getAccount()))
    assert printerIdNoneTest is None


def test_addPrinterFails():
    global printerManagerInstance
    assert printerManagerInstance.addPrinter('', None, '') is False


def test_invalidRequest():
    testMock = MockRequestor()
    assert testMock.doRequest('thisrequestisinvalid') is None


def test_printers():
    global printerManagerInstance, requestors

    # test cups connection
    connection = cups.Connection()
    cupsprinters = connection.getPrinters()

    # total printer
    totalPrinters = 0
    for requestor in requestors:
        totalPrinters += len(requestor.printers)

    # test getting printers for specific account
    printersforaccount = printerManagerInstance.getPrinters(requestors[1].getAccount())
    assert len(printersforaccount) == len(requestors[1].printers)

    printers = printerManagerInstance.getPrinters()
    import re
    assert len(printers) == totalPrinters
    for printer in printers:

        # name
        assert isinstance(printer['name'], basestring)
        assert len(printer['name']) > 0

        # account
        assert isinstance(printer.getAccount(), basestring)
        assert len(printer.getAccount()) > 0

        # id
        assert isinstance(printer['id'], basestring)
        assert len(printer['id']) > 0

        # test encoding and decoding printer details to/from uri
        uritest = re.compile(
            Utils.PROTOCOL + "(.*)/" + urllib.quote(printer['id']))
        assert isinstance(printer.getURI(), basestring)
        assert len(printer.getURI()) > 0
        assert uritest.match(printer.getURI()) is not None

        accountName, printerId = printerManagerInstance._getAccountNameAndPrinterIdFromURI(
            printer.getURI())
        assert isinstance(accountName, basestring)
        assert isinstance(printerId, basestring)
        assert accountName == printer.getAccount()
        assert printerId == printer['id']

        # get ppd
        ppdid = 'MFG:Google;DRV:GCP;CMD:POSTSCRIPT;DES:GoogleCloudPrint;MDL'
        ppds = connection.getPPDs(ppd_device_id=ppdid)
        printerppdname, printerppd = ppds.popitem()

        # test add printer to cups
        assert printerManagerInstance.addPrinter(
            printer['name'],
            printer,
            "test location",
            printerppdname) is not None
        testprintername = printerManagerInstance.sanitizePrinterName(printer['name'])

        # test printer actually added to cups
        cupsPrinters = connection.getPrinters()
        found = False
        for cupsPrinter in cupsPrinters:
            if (cupsPrinters[cupsPrinter]['printer-info'] == testprintername):
                found = True
                break

        assert found is True

        # delete test printer
        connection.deletePrinter(testprintername)
