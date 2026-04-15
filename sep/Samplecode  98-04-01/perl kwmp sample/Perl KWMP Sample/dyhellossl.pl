#!/usr/local/perl 

# -- SOAP::Lite -- soaplite.com -- Copyright (C) 2001 Paul Kulchenko --

BEGIN { warn "Started...\n" }

# import interface. All methods from loaded service are imported by default
use Crypt::SSLeay;
use SOAP::Lite
  service => 'https://acquirer.samanepay.com/payments/referencepayment.asmx?WSDL',
  # service => 'file:/your/local/path/xmethods-delayed-quotes.wsdl',
  # service => 'file:./xmethods-delayed-quotes.wsdl',
   on_fault => sub { my($soap, $res) = @_;
    die ref $res ? $res->faultdetail : $soap->transport->status, "\n";
   }
;

#$ENV{HTTPS_CA_FILE} = './server.crt' ;
#$ENV{HTTPS_CERT_FILE} = './cacert.pem' ;

warn "Loaded...\n";
print sayHello('houmane ablah'), "\n";
print AddSeller('127.0.0.1','hasan','hasan','hasan'), "\n";

