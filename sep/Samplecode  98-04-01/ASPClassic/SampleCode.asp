<%
'=======================================================================================
'=== SAMPLE code showing how to consume KWMP web services
'=======================================================================================
%>
<html>
<META http-equiv=Content-Type content='text/html; charset=windows-1256'>
<head>
<title></title>
</head>
<body >
<%

'=== Create an instance of SoapClient
SET objSoapClient = Server.CreateObject("MSSOAP.SoapClient30")
'=== Set Client Properties
objSoapClient.ClientProperty("ServerHTTPRequest") = True

'=== Retrieve KWMP web services WSDL
Call objSoapClient.mssoapinit("https://acquirer.samanepay.com/payment.aspx/referencepayment.asmx?WSDL","PaymentIFBinding")
'=== Set connection property to be over SSL
objSoapClient.ConnectorProperty("UseSSL") = True 

'=== Now consume the web sevices according to KWMP Specification
output = objSoapClient.verifyTransaction ("Reference Number","Merchant ID")

%>
<BR><BR>
</body>
</html>


