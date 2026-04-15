import refpayclient.*;

public class useit
{
	public static void main( String[] args ){
		
		RefClient myclient = new RefClient("https://acquirer.samanepay.com/payments/referencepayment.asmx","Full Path Of the .jks file",".jks password");
		double res ;
		res = myclient.verifyTransaction("Reference Code", "Your MTID" );
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
			
