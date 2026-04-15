import refpayclient.*;

public class useit
{
	public static void main( String[] args ){
		
		RefClient myclient = new RefClient("https://acquirer.samanepay.com/payments/referencepayment.asmx","/etc/saman.jks","changeit");
		double res ;
		res = myclient.verifyTransaction("11111111111111111111", "00025004-02" );
		if( res < 0 ) 
		{
			System.out.println("verify failed "+res);
		}
		else
		{
			System.out.println("verify succeded, amount is:");
			System.out.println(res);
		}
			
		
	}
}
			
