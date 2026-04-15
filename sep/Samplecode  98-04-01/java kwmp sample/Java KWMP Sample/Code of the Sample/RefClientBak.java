

package refpayclient;

import javax.xml.rpc.Stub;

public class RefClient {

    private String endpointAddress;

    public static  void main(String[] args) {  //it first was public static void

        System.out.println("Endpoint address = " + args[0]);
        try {
            Stub stub = createProxy();
            stub._setProperty(javax.xml.rpc.Stub.ENDPOINT_ADDRESS_PROPERTY, 
                args[0]); 
            PaymentIF pay = (PaymentIF)stub;
            System.out.println(pay.sayHello("Duke!"));
        } catch (Exception ex) {
            ex.printStackTrace();
        }
    }    

    private static  Stub createProxy() {   //if was first static
        // Note: MyHelloService_Impl is implementation-specific.
        return (Stub)(new ReferencePayment_Impl().getPaymentIFPort());
    }
}
