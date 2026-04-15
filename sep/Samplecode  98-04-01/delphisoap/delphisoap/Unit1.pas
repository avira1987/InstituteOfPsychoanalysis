unit Unit1;

interface

uses
  Windows, Messages, SysUtils, Variants, Classes, Graphics, Controls, Forms,
  Dialogs, IdBaseComponent, IdComponent, IdTCPConnection, IdTCPClient,
  IdTelnet, MSSOAPLib30_TLB, StdCtrls, ComObj;

type
  TForm1 = class(TForm)
    Button1: TButton;
    
    procedure initiateConnction();
    procedure Button1Click(Sender: TObject);

  private
    { Private declarations }
  public
    { Public declarations }
  end;

var
  Form1: TForm1;
  V: OleVariant;

implementation

{$R *.dfm}

procedure TForm1.initiateConnction ;
begin
                V := CoSoapClient30.Create;
                V.mssoapinit('https://acquirer.samanepay.com/payments/referencepayment.asmx?WSDL','ReferencePayment');
end;

procedure TForm1.Button1Click(Sender: TObject);
var

        //V: ISoapClient;
        res : integer ;
        resStr : string ;
begin
        try

                V := CoSoapClient30.Create;
                V.mssoapinit('https://acquirer.samanepay.com/payments/referencepayment.asmx?WSDL','ReferencePayment');

                res := V.verifyTransaction('aaaaaaaaaaaaaaaaaaaa'{ReferenceNumber}, '802-800-19-1'{buyeracc,optional}, '802-800-19105-1'{selleracc});
                resStr := IntToStr(res);
                MessageDlg(resStr,mtInformation,[mbOk],0);

                res := V.reverseTransaction('aaaaaaaaaaaaaaaaaaaa', '802-800-19-1', '802-800-19105-1','mypass');
                resStr := IntToStr(res);
                MessageDlg(resStr,mtInformation,[mbOk],0);

                res := V.partialReverseTransaction('aaaaaaaaaaaaaaaaaaaa', '802-800-19-1', '802-800-19105-1','mypass'{password},10{amount});
                resStr := IntToStr(res);
                MessageDlg(resStr,mtInformation,[mbOk],0);

         except on E: Exception do
                MessageDlg(E.Message,mtInformation,[mbOk],0);
        end;

end;



end.
