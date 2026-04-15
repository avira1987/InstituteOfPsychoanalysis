#!/usr/bin/perl 

# -- SOAP::Lite -- soaplite.com -- Copyright (C) 2001 Paul Kulchenko --

# stub interface (created with stubmaker.pl)
# perl stubmaker.pl http://www.xmethods.net/sd/StockQuoteService.wsdl

use MyHelloService;

my $service = MyHelloService->new;
print $service->sayHello('Ahmad Khan'), "\n";
