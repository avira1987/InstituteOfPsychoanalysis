package refpayclient;

import javax.xml.rpc.Stub;

public class RefClient {

    private String endpointAddress;
    private String caStore;
    private String storePassword;
    private Stub stub;


    public RefClient(String i_strEndpointAddress, String i_strCaStore, String i_strStorePassword) {
        endpointAddress = i_strEndpointAddress;
        caStore = i_strCaStore;
        storePassword = i_strStorePassword;
        stub = null;
    }


    public double doQuery(String i_strRefNum, String i_strBuyerAcc, String i_strSellerAcc) {

        try {


            if (i_strRefNum.equals("")) {
                System.out.println("Ref Num can't be empty");
                return -1;
            }

            if (i_strSellerAcc.equals("")) {
                System.out.println("seller acc cant be empty");
                return -1;
            }

            stub = createProxy();

            System.setProperty("javax.net.ssl.trustStore", caStore);
            System.setProperty("javax.net.ssl.trustStorePassword", storePassword);

            stub._setProperty(javax.xml.rpc.Stub.ENDPOINT_ADDRESS_PROPERTY,
                    endpointAddress);
            PaymentIF pay = (PaymentIF) stub;
            double res;
            res = pay.verifyTransaction(i_strRefNum, i_strBuyerAcc, i_strSellerAcc);
            System.out.println("result is:");
            System.out.println(res);
            return res;
        } catch (Throwable ex) {
            System.out.println("In doQuery" + ex.getMessage());
            return -1;
        }
    }

    private Stub createProxy() {   //if was first static
        // Note: MyHelloService_Impl is implementation-specific.
        return (Stub) (new ReferencePayment_Impl().getPaymentIFPort());
    }
}
