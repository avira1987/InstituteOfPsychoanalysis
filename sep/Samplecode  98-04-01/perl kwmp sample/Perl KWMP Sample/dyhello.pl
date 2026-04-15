#!/usr/local/perl 

# -- SOAP::Lite -- soaplite.com -- Copyright (C) 2001 Paul Kulchenko --

BEGIN { warn "Started...\n" }

# import interface. All methods from loaded service are imported by default
#use Crypt::SSLeay;
use SOAP::Lite
  service => 'https://acquirer.samanepay.com/payments/referencepayment.asmx?WSDL',
  # service => 'file:/your/local/path/xmethods-delayed-quotes.wsdl',
  # service => 'file:./xmethods-delayed-quotes.wsdl',
   on_fault => sub { my($soap, $res) = @_;
    die ref $res ? $res->faultdetail : $soap->transport->status, "\n";
   }
;

#$ENV{HTTPS_CA_FILE} = './cacert.pem' ;
#$ENV{HTTPS_CERT_FILE} = './cacert.pem' ;

warn "Loaded...\n";

#$res = verifyTransaction('T8qrtY6bK81mcAe2y0tH','00015001-28');
#$res = verifyTransaction('aaaaaaaaaaaaaaaaaaaaa','802-800-201255-1','802-800-5655-1');
#if( $res > 0 )
#{
#	printf("this transaction is valid with amount: $res\n");
#}
#else
#{
#	printf("this transaction was failed with error: $res\n");
#}

# refnum,buyeracc, selleracc, password
$res = reverseTransaction('+S3aW4ycCNewgbEHhZNG','00015004-29','654321',1.1) ;
if( $res == 1 )
{
	printf("reverse was successfull, with result: $res \n");
}
else
{
	printf ("reverse doc failed and result is: $res \n");
}


