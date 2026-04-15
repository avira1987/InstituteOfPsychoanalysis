unit MSSOAPLib30_TLB;

// ************************************************************************ //
// WARNING                                                                    
// -------                                                                    
// The types declared in this file were generated from data read from a       
// Type Library. If this type library is explicitly or indirectly (via        
// another type library referring to this type library) re-imported, or the   
// 'Refresh' command of the Type Library Editor activated while editing the   
// Type Library, the contents of this file will be regenerated and all        
// manual modifications will be lost.                                         
// ************************************************************************ //

// PASTLWTR : $Revision:   1.130  $
// File generated on 2004/02/22 06:03:12 È.Ù from Type Library described below.

// ************************************************************************  //
// Type Lib: C:\Program Files\Common Files\MSSoap\Binaries\MSSOAP30.dll (1)
// LIBID: {91147A58-DFE4-47C0-8E76-987FC1A6001B}
// LCID: 0
// Helpfile: 
// DepndLst: 
//   (1) v2.0 stdole, (C:\WINNT\System32\stdole2.tlb)
//   (2) v4.0 MSXML2, (C:\WINNT\system32\msxml4.dll)
//   (3) v4.0 StdVCL, (C:\WINNT\System32\stdvcl40.dll)
// Errors:
//   Hint: Member 'Property' of 'IParserSource' changed to 'Property_'
//   Hint: Member 'Property' of 'IAttachment' changed to 'Property_'
//   Hint: Member 'Property' of 'IComposerDestination' changed to 'Property_'
//   Hint: Member 'type' of 'tagSTATSTG' changed to 'type_'
//   Hint: Member 'String' of 'IStringAttachment' changed to 'String_'
//   Hint: Member 'Array' of 'IByteArrayAttachment' changed to 'Array_'
//   Hint: Member 'type' of 'IWSDLOperation' changed to 'type_'
//   Hint: Member 'Property' of 'ISoapConnector' changed to 'Property_'
// ************************************************************************ //
{$TYPEDADDRESS OFF} // Unit must be compiled without type-checked pointers. 
{$WARN SYMBOL_PLATFORM OFF}
{$WRITEABLECONST ON}

interface

uses ActiveX, Classes, Graphics, MSXML2_TLB, OleServer, StdVCL, Variants, 
Windows;
  

// *********************************************************************//
// GUIDS declared in the TypeLibrary. Following prefixes are used:        
//   Type Libraries     : LIBID_xxxx                                      
//   CoClasses          : CLASS_xxxx                                      
//   DISPInterfaces     : DIID_xxxx                                       
//   Non-DISP interfaces: IID_xxxx                                        
// *********************************************************************//
const
  // TypeLibrary Major and minor versions
  MSSOAPLib30MajorVersion = 3;
  MSSOAPLib30MinorVersion = 0;

  LIBID_MSSOAPLib30: TGUID = '{91147A58-DFE4-47C0-8E76-987FC1A6001B}';

  IID_ISoapReader: TGUID = '{B21F31CA-0F45-4046-A231-CFB386E9E45F}';
  IID_IMessageParser: TGUID = '{3B2A98E6-F76A-48B1-8F7D-0139A8D0258C}';
  IID_IParserSource: TGUID = '{282C694F-D69F-4044-B076-6F4AC1748A90}';
  IID_ISequentialStream: TGUID = '{0C733A30-2A1C-11CE-ADE5-00AA0044773D}';
  IID_IReceivedAttachments: TGUID = '{176B81CD-4F22-4CA0-9F54-9FE5935A595B}';
  IID_IAttachment: TGUID = '{A2C40FB2-B768-4EC8-809A-6ECB4B89C6A7}';
  IID_IReceivedAttachment: TGUID = '{C0C9F1C0-0039-427B-8ACC-AD172FE557A8}';
  IID_ISoapMapper: TGUID = '{C1E6061A-F8DC-4CA8-A952-FAF7419F1029}';
  IID_ISoapSerializer: TGUID = '{23BDF2B5-2304-4550-BBE2-F197E2CC47B6}';
  IID_IMessageComposer: TGUID = '{906A72B9-FF88-4A49-AFA2-CC4CAB5104EC}';
  IID_IComposerDestination: TGUID = '{8E62C4B1-EE0C-48FB-9161-3EE041A03153}';
  IID_IDataEncoder: TGUID = '{663EB158-8D95-4657-AE32-B7C60DE6122F}';
  IID_IStream: TGUID = '{0000000C-0000-0000-C000-000000000046}';
  IID_IDataEncoderFactory: TGUID = '{456C5AB4-2A2A-4289-9D4C-0C28BF739EE4}';
  IID_IFileAttachment: TGUID = '{D6DEA9EB-28EA-45C7-A46A-72D26668C1EA}';
  CLASS_FileAttachment30: TGUID = '{90A299F3-26C6-457D-A514-404335109EDD}';
  IID_IStringAttachment: TGUID = '{8004A743-6A1E-45E4-B2E2-A6D117F06008}';
  CLASS_StringAttachment30: TGUID = '{722C5A81-4FEC-43F7-8656-E16EC6853073}';
  IID_IByteArrayAttachment: TGUID = '{52088645-8E96-4C18-8621-B46611635303}';
  CLASS_ByteArrayAttachment30: TGUID = '{565FBBE9-8563-4302-BE8A-7C6A64FB0A85}';
  IID_IStreamAttachment: TGUID = '{BE1DBCF5-2260-470A-8E1C-E2406D106E0A}';
  CLASS_StreamAttachment30: TGUID = '{05AE7FB3-C4E9-4F79-A5C3-DAB525E31F2C}';
  IID_ISentAttachments: TGUID = '{95A098C0-EB61-4895-91C7-78873251322E}';
  CLASS_SentAttachments30: TGUID = '{CE071800-E681-4ADF-9422-A3D0BD0D51CB}';
  CLASS_ReceivedAttachments30: TGUID = '{AF9B6377-6505-4934-AD85-BAB87E15EF65}';
  IID_IGetComposerDestination: TGUID = '{9E6CDFEF-4C42-411B-BACA-FE96F7A13C04}';
  IID_IDimeComposer: TGUID = '{ABAADE34-EEF6-408A-8896-65BE669D27FA}';
  IID_ISimpleComposer: TGUID = '{70824404-7A18-412A-9A83-A9EC0F3FF045}';
  IID_IGetParserSource: TGUID = '{BB63287E-1407-40E3-89AB-38CB2746547F}';
  IID_IDimeParser: TGUID = '{E3F8BAA5-8A05-4641-91CE-3FBC533D1EDB}';
  IID_ISimpleParser: TGUID = '{B313A227-0798-4A87-9074-48CA2164D0F7}';
  CLASS_DataEncoderFactory30: TGUID = '{7A51A663-4790-4885-B0E4-124D4BDADB3E}';
  CLASS_DimeComposer30: TGUID = '{B85E6E71-1493-442F-BC97-B511BE0D5D96}';
  CLASS_DimeParser30: TGUID = '{DFC2FA0B-CC72-4486-B9F4-06FE8A75D58F}';
  CLASS_SimpleComposer30: TGUID = '{F7E00C3F-D6C7-4E53-9887-61A2D4EBF0E8}';
  CLASS_SimpleParser30: TGUID = '{4D602A27-DC39-45D6-A6B1-7003DE2E173C}';
  CLASS_SoapReader30: TGUID = '{A8D986B6-9257-11D5-87EA-00B0D0BE6479}';
  CLASS_SoapSerializer30: TGUID = '{B76585B0-9257-11D5-87EA-00B0D0BE6479}';
  IID_ISoapClient: TGUID = '{7F017F92-9257-11D5-87EA-00B0D0BE6479}';
  IID_ISoapServer: TGUID = '{7F017F93-9257-11D5-87EA-00B0D0BE6479}';
  CLASS_SoapServer30: TGUID = '{7F017F96-9257-11D5-87EA-00B0D0BE6479}';
  CLASS_SoapClient30: TGUID = '{7F017F97-9257-11D5-87EA-00B0D0BE6479}';
  IID_ISoapTypeMapperFactory: TGUID = '{FCED9F15-D0A7-4380-87E6-992381ACD213}';
  IID_ISoapTypeMapper: TGUID = '{29D3F736-1C25-44EE-9CEE-3F52F226BA8A}';
  IID_IHeaderHandler: TGUID = '{504D4B91-76B8-4D88-95EA-CEB5E0FE41F3}';
  IID_IEnumSoapMappers: TGUID = '{ACDDCED6-6DB8-497A-BF10-068711629924}';
  IID_IWSDLMessage: TGUID = '{49F9421C-DC88-43E1-825F-70E788E9A9A9}';
  IID_IWSDLOperation: TGUID = '{A0B762A7-9F3E-48D8-B333-770E5FA72A1E}';
  IID_IEnumWSDLOperations: TGUID = '{B0BBA669-55F7-4E9C-941E-49BC4715C834}';
  IID_IWSDLPort: TGUID = '{4D40B730-F5FA-472C-8819-DDCD183BD0DE}';
  IID_IEnumWSDLPorts: TGUID = '{EC189C1C-31B3-4193-BDCA-98EC44FF3EE0}';
  IID_IWSDLService: TGUID = '{9B5D8D63-EA54-41F6-9F12-F77A13111EC6}';
  IID_IEnumWSDLService: TGUID = '{104F6816-093E-41D7-A68B-8E1CC408B279}';
  IID_IWSDLReader: TGUID = '{DE523FD4-AFB8-4643-BA90-9DEB3C7FB4A3}';
  IID_IWSDLBinding: TGUID = '{AB0E0268-304D-43FC-8603-B1105F3A7512}';
  CLASS_WSDLReader30: TGUID = '{EF90A70C-925B-11D5-87EA-00B0D0BE6479}';
  CLASS_SoapTypeMapperFactory30: TGUID = '{EF90A715-925B-11D5-87EA-00B0D0BE6479}';
  CLASS_GenericCustomTypeMapper30: TGUID = '{EF90A716-925B-11D5-87EA-00B0D0BE6479}';
  CLASS_UDTMapper30: TGUID = '{8BCD9554-86C7-435D-A8C8-BCB3C72FBEE9}';
  IID_ISoapConnector: TGUID = '{0AF40C4E-9257-11D5-87EA-00B0D0BE6479}';
  IID_ISoapConnectorFactory: TGUID = '{0AF40C50-9257-11D5-87EA-00B0D0BE6479}';
  CLASS_SoapConnector30: TGUID = '{0AF40C52-9257-11D5-87EA-00B0D0BE6479}';
  CLASS_SoapConnectorFactory30: TGUID = '{0AF40C58-9257-11D5-87EA-00B0D0BE6479}';
  CLASS_HttpConnector30: TGUID = '{0AF40C53-9257-11D5-87EA-00B0D0BE6479}';
  IID_ISoapError: TGUID = '{7F017F94-9257-11D5-87EA-00B0D0BE6479}';
  IID_IErrorInfo: TGUID = '{1CF2B120-547D-101B-8E65-08002B2BD119}';
  IID_ISoapErrorInfo: TGUID = '{C0871607-8C99-4824-92CD-85CBD4C7273F}';
  IID_IGCTMObjectFactory: TGUID = '{3C87B8BE-F2B7-45C5-B34E-4A46A58A80B0}';

// *********************************************************************//
// Declaration of Enumerations defined in Type Library                    
// *********************************************************************//
// Constants for enum __MIDL___MIDL_itf_mssoap30_0135_0001
type
  __MIDL___MIDL_itf_mssoap30_0135_0001 = TOleEnum;
const
  smInput = $FFFFFFFF;
  smOutput = $00000000;
  smInOut = $00000001;

// Constants for enum __MIDL___MIDL_itf_mssoap30_0135_0003
type
  __MIDL___MIDL_itf_mssoap30_0135_0003 = TOleEnum;
const
  enXSDUndefined = $FFFFFFFF;
  enXSDDOM = $00000000;
  enXSDstring = $00000001;
  enXSDboolean = $00000002;
  enXSDfloat = $00000003;
  enXSDDouble = $00000004;
  enXSDdecimal = $00000005;
  enXSDtimeDuration = $00000006;
  enXSDduration = $00000006;
  enXSDrecurringDuration = $00000007;
  enXSDbinary = $00000008;
  enXSDbase64binary = $00000008;
  enXSDuriReference = $00000009;
  enXSDanyURI = $00000009;
  enXSDid = $0000000A;
  enXSDidRef = $0000000B;
  enXSDentity = $0000000C;
  enXSDQName = $0000000D;
  enXSDcdata = $0000000E;
  enXSDnormalizedString = $0000000E;
  enXSDtoken = $0000000F;
  enXSDlanguage = $00000010;
  enXSDidRefs = $00000011;
  enXSDentities = $00000012;
  enXSDnmtoken = $00000013;
  enXSDnmtokens = $00000014;
  enXSDname = $00000015;
  enXSDncname = $00000016;
  enXSDnotation = $00000017;
  enXSDinteger = $00000018;
  enXSDnonpositiveInteger = $00000019;
  enXSDlong = $0000001A;
  enXSDint = $0000001B;
  enXSDshort = $0000001C;
  enXSDbyte = $0000001D;
  enXSDnonNegativeInteger = $0000001E;
  enXSDnegativeInteger = $0000001F;
  enXSDunsignedLong = $00000020;
  enXSDunsignedInt = $00000021;
  enXSDunsignedShort = $00000022;
  enXSDunsignedByte = $00000023;
  enXSDpositiveInteger = $00000024;
  enXSDtimeInstant = $00000025;
  enXSDdatetime = $00000025;
  enXSDtime = $00000026;
  enXSDtimePeriod = $00000027;
  enXSDdate = $00000028;
  enXSDmonth = $00000029;
  enXSDgMonth = $00000029;
  enXSDgYearMonth = $00000029;
  enXSDyear = $0000002A;
  enXSDgYear = $0000002A;
  enXSDcentury = $0000002B;
  enXSDrecurringDate = $0000002C;
  enXSDgMonthDay = $0000002C;
  enXSDrecurringDay = $0000002D;
  enXSDgDay = $0000002D;
  enXSDarray = $0000002E;
  enXSDanyType = $0000002F;
  enTKempty = $00000030;
  enXSDhexbinary = $00000031;
  enXSDEndOfBuildin = $00000032;

// Constants for enum __MIDL___MIDL_itf_mssoap30_0135_0002
type
  __MIDL___MIDL_itf_mssoap30_0135_0002 = TOleEnum;
const
  stNone = $00000000;
  stAttachment = $00000001;
  stSentAttachments = $00000002;
  stReceivedAttachments = $00000003;

// Constants for enum __MIDL___MIDL_itf_mssoap30_0000_0001
type
  __MIDL___MIDL_itf_mssoap30_0000_0001 = TOleEnum;
const
  cdMayRequireResend = $00000001;
  cdRequiresTotalSize = $00000002;

// Constants for enum __MIDL___MIDL_itf_mssoap30_0132_0001
type
  __MIDL___MIDL_itf_mssoap30_0132_0001 = TOleEnum;
const
  elDefaultLocation = $00000000;
  elEndOfEnvelope = $00000001;
  elEndOfBody = $00000002;
  elEndOfHeader = $00000003;

// Constants for enum __MIDL___MIDL_itf_mssoap30_0135_0004
type
  __MIDL___MIDL_itf_mssoap30_0135_0004 = TOleEnum;
const
  enDocumentLiteral = $00000000;
  enDocumentEncoded = $00000001;
  enRPCLiteral = $00000002;
  enRPCEncoded = $00000004;

// Constants for enum __MIDL___MIDL_itf_mssoap30_0135_0005
type
  __MIDL___MIDL_itf_mssoap30_0135_0005 = TOleEnum;
const
  enOneWay = $00000000;
  enRequestResponse = $00000001;

type

// *********************************************************************//
// Forward declaration of types defined in TypeLibrary                    
// *********************************************************************//
  ISoapReader = interface;
  ISoapReaderDisp = dispinterface;
  IMessageParser = interface;
  IParserSource = interface;
  ISequentialStream = interface;
  IReceivedAttachments = interface;
  IReceivedAttachmentsDisp = dispinterface;
  IAttachment = interface;
  IAttachmentDisp = dispinterface;
  IReceivedAttachment = interface;
  IReceivedAttachmentDisp = dispinterface;
  ISoapMapper = interface;
  ISoapSerializer = interface;
  ISoapSerializerDisp = dispinterface;
  IMessageComposer = interface;
  IComposerDestination = interface;
  IDataEncoder = interface;
  IDataEncoderDisp = dispinterface;
  IStream = interface;
  IDataEncoderFactory = interface;
  IDataEncoderFactoryDisp = dispinterface;
  IFileAttachment = interface;
  IFileAttachmentDisp = dispinterface;
  IStringAttachment = interface;
  IStringAttachmentDisp = dispinterface;
  IByteArrayAttachment = interface;
  IByteArrayAttachmentDisp = dispinterface;
  IStreamAttachment = interface;
  IStreamAttachmentDisp = dispinterface;
  ISentAttachments = interface;
  ISentAttachmentsDisp = dispinterface;
  IGetComposerDestination = interface;
  IDimeComposer = interface;
  IDimeComposerDisp = dispinterface;
  ISimpleComposer = interface;
  ISimpleComposerDisp = dispinterface;
  IGetParserSource = interface;
  IDimeParser = interface;
  IDimeParserDisp = dispinterface;
  ISimpleParser = interface;
  ISimpleParserDisp = dispinterface;
  ISoapClient = interface;
  ISoapClientDisp = dispinterface;
  ISoapServer = interface;
  ISoapServerDisp = dispinterface;
  ISoapTypeMapperFactory = interface;
  ISoapTypeMapperFactoryDisp = dispinterface;
  ISoapTypeMapper = interface;
  ISoapTypeMapperDisp = dispinterface;
  IHeaderHandler = interface;
  IHeaderHandlerDisp = dispinterface;
  IEnumSoapMappers = interface;
  IWSDLMessage = interface;
  IWSDLOperation = interface;
  IEnumWSDLOperations = interface;
  IWSDLPort = interface;
  IEnumWSDLPorts = interface;
  IWSDLService = interface;
  IEnumWSDLService = interface;
  IWSDLReader = interface;
  IWSDLBinding = interface;
  ISoapConnector = interface;
  ISoapConnectorDisp = dispinterface;
  ISoapConnectorFactory = interface;
  ISoapConnectorFactoryDisp = dispinterface;
  ISoapError = interface;
  IErrorInfo = interface;
  ISoapErrorInfo = interface;
  IGCTMObjectFactory = interface;

// *********************************************************************//
// Declaration of CoClasses defined in Type Library                       
// (NOTE: Here we map each CoClass to its Default Interface)              
// *********************************************************************//
  FileAttachment30 = IFileAttachment;
  StringAttachment30 = IStringAttachment;
  ByteArrayAttachment30 = IByteArrayAttachment;
  StreamAttachment30 = IStreamAttachment;
  SentAttachments30 = ISentAttachments;
  ReceivedAttachments30 = IReceivedAttachments;
  DataEncoderFactory30 = IDataEncoderFactory;
  DimeComposer30 = IDimeComposer;
  DimeParser30 = IDimeParser;
  SimpleComposer30 = ISimpleComposer;
  SimpleParser30 = ISimpleParser;
  SoapReader30 = ISoapReader;
  SoapSerializer30 = ISoapSerializer;
  SoapServer30 = ISoapServer;
  SoapClient30 = ISoapClient;
  WSDLReader30 = IWSDLReader;
  SoapTypeMapperFactory30 = ISoapTypeMapperFactory;
  GenericCustomTypeMapper30 = IDispatch;
  UDTMapper30 = IDispatch;
  SoapConnector30 = ISoapConnector;
  SoapConnectorFactory30 = ISoapConnectorFactory;
  HttpConnector30 = ISoapConnector;


// *********************************************************************//
// Declaration of structures, unions and aliases.                         
// *********************************************************************//
  PByte1 = ^Byte; {*}
  POleVariant1 = ^OleVariant; {*}
  PWord1 = ^Word; {*}
  PInteger1 = ^Integer; {*}
  PWideString1 = ^WideString; {*}
  PPUserType1 = ^IXMLDOMNode; {*}
  PPUserType2 = ^IMessageComposer; {*}
  PPUserType3 = ^IMessageParser; {*}
  PUINT1 = ^LongWord; {*}
  PHResult1 = ^HResult; {*}

  smIsInputEnum = __MIDL___MIDL_itf_mssoap30_0135_0001; 
  enXSDType = __MIDL___MIDL_itf_mssoap30_0135_0003; 
  enSpecialType = __MIDL___MIDL_itf_mssoap30_0135_0002; 
  ComposerDestinationFlags = __MIDL___MIDL_itf_mssoap30_0000_0001; 
  enElementLocation = __MIDL___MIDL_itf_mssoap30_0132_0001; 
  enEncodingStyle = __MIDL___MIDL_itf_mssoap30_0135_0004; 

  _LARGE_INTEGER = packed record
    QuadPart: Int64;
  end;

  _ULARGE_INTEGER = packed record
    QuadPart: Largeuint;
  end;

  _FILETIME = packed record
    dwLowDateTime: LongWord;
    dwHighDateTime: LongWord;
  end;

  tagSTATSTG = packed record
    pwcsName: PWideChar;
    type_: LongWord;
    cbSize: _ULARGE_INTEGER;
    mtime: _FILETIME;
    ctime: _FILETIME;
    atime: _FILETIME;
    grfMode: LongWord;
    grfLocksSupported: LongWord;
    clsid: TGUID;
    grfStateBits: LongWord;
    reserved: LongWord;
  end;

  enOperationType = __MIDL___MIDL_itf_mssoap30_0135_0005; 

// *********************************************************************//
// Interface: ISoapReader
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {B21F31CA-0F45-4046-A231-CFB386E9E45F}
// *********************************************************************//
  ISoapReader = interface(IDispatch)
    ['{B21F31CA-0F45-4046-A231-CFB386E9E45F}']
    function  Load(par_source: OleVariant; const par_soapAction: WideString): WordBool; safecall;
    function  LoadWithParser(par_source: OleVariant; const par_parser: IMessageParser; 
                             const par_soapAction: WideString): WordBool; safecall;
    function  LoadXml(const par_xml: WideString): WordBool; safecall;
    function  Get_Dom: IXMLDOMDocument; safecall;
    function  Get_Envelope: IXMLDOMElement; safecall;
    function  Get_Body: IXMLDOMElement; safecall;
    function  Get_Header: IXMLDOMElement; safecall;
    function  Get_Fault: IXMLDOMElement; safecall;
    function  Get_FaultString: IXMLDOMElement; safecall;
    function  Get_FaultCode: IXMLDOMElement; safecall;
    function  Get_FaultActor: IXMLDOMElement; safecall;
    function  Get_FaultDetail: IXMLDOMElement; safecall;
    function  Get_HeaderEntry(const par_LocalName: WideString; const par_NamespaceURI: WideString): IXMLDOMElement; safecall;
    function  Get_MustUnderstandHeaderEntries: IXMLDOMNodeList; safecall;
    function  Get_HeaderEntries: IXMLDOMNodeList; safecall;
    function  Get_BodyEntries: IXMLDOMNodeList; safecall;
    function  Get_BodyEntry(const par_LocalName: WideString; const par_NamespaceURI: WideString): IXMLDOMElement; safecall;
    function  Get_RpcStruct: IXMLDOMElement; safecall;
    function  Get_RpcParameter(const par_LocalName: WideString; const par_NamespaceURI: WideString): IXMLDOMElement; safecall;
    function  Get_RpcResult: IXMLDOMElement; safecall;
    function  Get_SoapAction: WideString; safecall;
    function  GetContextItem(const par_key: WideString): OleVariant; safecall;
    procedure SetContextItem(const par_key: WideString; par_value: OleVariant); safecall;
    function  Get_Attachments: IReceivedAttachments; safecall;
    function  GetReferencedNode(const par_context: IXMLDOMNode): IXMLDOMNode; safecall;
    function  GetReferencedAttachment(const par_context: IXMLDOMNode): IAttachment; safecall;
    function  IsAttachmentReference(const par_context: IXMLDOMNode): WordBool; safecall;
    function  IsNodeReference(const par_context: IXMLDOMNode): WordBool; safecall;
    function  Get_Parser: IMessageParser; safecall;
    procedure Set_XmlVersion(const Param1: WideString); safecall;
    property Dom: IXMLDOMDocument read Get_Dom;
    property Envelope: IXMLDOMElement read Get_Envelope;
    property Body: IXMLDOMElement read Get_Body;
    property Header: IXMLDOMElement read Get_Header;
    property Fault: IXMLDOMElement read Get_Fault;
    property FaultString: IXMLDOMElement read Get_FaultString;
    property FaultCode: IXMLDOMElement read Get_FaultCode;
    property FaultActor: IXMLDOMElement read Get_FaultActor;
    property FaultDetail: IXMLDOMElement read Get_FaultDetail;
    property HeaderEntry[const par_LocalName: WideString; const par_NamespaceURI: WideString]: IXMLDOMElement read Get_HeaderEntry;
    property MustUnderstandHeaderEntries: IXMLDOMNodeList read Get_MustUnderstandHeaderEntries;
    property HeaderEntries: IXMLDOMNodeList read Get_HeaderEntries;
    property BodyEntries: IXMLDOMNodeList read Get_BodyEntries;
    property BodyEntry[const par_LocalName: WideString; const par_NamespaceURI: WideString]: IXMLDOMElement read Get_BodyEntry;
    property RpcStruct: IXMLDOMElement read Get_RpcStruct;
    property RpcParameter[const par_LocalName: WideString; const par_NamespaceURI: WideString]: IXMLDOMElement read Get_RpcParameter;
    property RpcResult: IXMLDOMElement read Get_RpcResult;
    property SoapAction: WideString read Get_SoapAction;
    property Attachments: IReceivedAttachments read Get_Attachments;
    property Parser: IMessageParser read Get_Parser;
  end;

// *********************************************************************//
// DispIntf:  ISoapReaderDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {B21F31CA-0F45-4046-A231-CFB386E9E45F}
// *********************************************************************//
  ISoapReaderDisp = dispinterface
    ['{B21F31CA-0F45-4046-A231-CFB386E9E45F}']
    function  Load(par_source: OleVariant; const par_soapAction: WideString): WordBool; dispid 1;
    function  LoadWithParser(par_source: OleVariant; const par_parser: IMessageParser; 
                             const par_soapAction: WideString): WordBool; dispid 2;
    function  LoadXml(const par_xml: WideString): WordBool; dispid 3;
    property Dom: IXMLDOMDocument readonly dispid 1610743811;
    property Envelope: IXMLDOMElement readonly dispid 1610743812;
    property Body: IXMLDOMElement readonly dispid 1610743813;
    property Header: IXMLDOMElement readonly dispid 1610743814;
    property Fault: IXMLDOMElement readonly dispid 1610743815;
    property FaultString: IXMLDOMElement readonly dispid 1610743816;
    property FaultCode: IXMLDOMElement readonly dispid 1610743817;
    property FaultActor: IXMLDOMElement readonly dispid 1610743818;
    property FaultDetail: IXMLDOMElement readonly dispid 1610743819;
    property HeaderEntry[const par_LocalName: WideString; const par_NamespaceURI: WideString]: IXMLDOMElement readonly dispid 1610743820;
    property MustUnderstandHeaderEntries: IXMLDOMNodeList readonly dispid 1610743821;
    property HeaderEntries: IXMLDOMNodeList readonly dispid 1610743822;
    property BodyEntries: IXMLDOMNodeList readonly dispid 1610743823;
    property BodyEntry[const par_LocalName: WideString; const par_NamespaceURI: WideString]: IXMLDOMElement readonly dispid 1610743824;
    property RpcStruct: IXMLDOMElement readonly dispid 1610743825;
    property RpcParameter[const par_LocalName: WideString; const par_NamespaceURI: WideString]: IXMLDOMElement readonly dispid 1610743826;
    property RpcResult: IXMLDOMElement readonly dispid 1610743827;
    property SoapAction: WideString readonly dispid 1610743828;
    function  GetContextItem(const par_key: WideString): OleVariant; dispid 1610743829;
    procedure SetContextItem(const par_key: WideString; par_value: OleVariant); dispid 1610743830;
    property Attachments: IReceivedAttachments readonly dispid 1610743831;
    function  GetReferencedNode(const par_context: IXMLDOMNode): IXMLDOMNode; dispid 1610743832;
    function  GetReferencedAttachment(const par_context: IXMLDOMNode): IAttachment; dispid 1610743833;
    function  IsAttachmentReference(const par_context: IXMLDOMNode): WordBool; dispid 1610743834;
    function  IsNodeReference(const par_context: IXMLDOMNode): WordBool; dispid 1610743835;
    property Parser: IMessageParser readonly dispid 1610743836;
    property XmlVersion: WideString writeonly dispid 1610743837;
  end;

// *********************************************************************//
// Interface: IMessageParser
// Flags:     (256) OleAutomation
// GUID:      {3B2A98E6-F76A-48B1-8F7D-0139A8D0258C}
// *********************************************************************//
  IMessageParser = interface(IUnknown)
    ['{3B2A98E6-F76A-48B1-8F7D-0139A8D0258C}']
    function  Initialize(const par_binding: IXMLDOMNode; const par_composer: IXMLDOMNode; 
                         const par_tempFolder: WideString; par_maxSize: Integer): HResult; stdcall;
    function  LoadMessage(const par_source: IParserSource; const par_envelope: ISequentialStream; 
                          out par_att: IReceivedAttachments): HResult; stdcall;
    function  LoadSpecialTypeMapper(const par_soapmapper: ISoapMapper; 
                                    const par_soapreader: ISoapReader; 
                                    const par_context: IXMLDOMNode): HResult; stdcall;
  end;

// *********************************************************************//
// Interface: IParserSource
// Flags:     (272) Hidden OleAutomation
// GUID:      {282C694F-D69F-4044-B076-6F4AC1748A90}
// *********************************************************************//
  IParserSource = interface(IUnknown)
    ['{282C694F-D69F-4044-B076-6F4AC1748A90}']
    function  Get_Property_(const par_name: WideString; out par_value: OleVariant): HResult; stdcall;
    function  Set_Property_(const par_name: WideString; par_value: OleVariant): HResult; stdcall;
    function  BeginReceiving(out par_stream: ISequentialStream): HResult; stdcall;
    function  EndReceiving: HResult; stdcall;
  end;

// *********************************************************************//
// Interface: ISequentialStream
// Flags:     (0)
// GUID:      {0C733A30-2A1C-11CE-ADE5-00AA0044773D}
// *********************************************************************//
  ISequentialStream = interface(IUnknown)
    ['{0C733A30-2A1C-11CE-ADE5-00AA0044773D}']
    function  RemoteRead(out pv: Byte; cb: LongWord; out pcbRead: LongWord): HResult; stdcall;
    function  RemoteWrite(var pv: Byte; cb: LongWord; out pcbWritten: LongWord): HResult; stdcall;
  end;

// *********************************************************************//
// Interface: IReceivedAttachments
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {176B81CD-4F22-4CA0-9F54-9FE5935A595B}
// *********************************************************************//
  IReceivedAttachments = interface(IDispatch)
    ['{176B81CD-4F22-4CA0-9F54-9FE5935A595B}']
    function  Get_Count: Integer; safecall;
    function  Get_Item(par_index: OleVariant): IAttachment; safecall;
    function  Get_ItemWithContext(par_index: OleVariant; const par_context: IXMLDOMNode): IAttachment; safecall;
    function  Get__NewEnum: IUnknown; safecall;
    property Count: Integer read Get_Count;
    property Item[par_index: OleVariant]: IAttachment read Get_Item; default;
    property ItemWithContext[par_index: OleVariant; const par_context: IXMLDOMNode]: IAttachment read Get_ItemWithContext;
    property _NewEnum: IUnknown read Get__NewEnum;
  end;

// *********************************************************************//
// DispIntf:  IReceivedAttachmentsDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {176B81CD-4F22-4CA0-9F54-9FE5935A595B}
// *********************************************************************//
  IReceivedAttachmentsDisp = dispinterface
    ['{176B81CD-4F22-4CA0-9F54-9FE5935A595B}']
    property Count: Integer readonly dispid 1610743808;
    property Item[par_index: OleVariant]: IAttachment readonly dispid 0; default;
    property ItemWithContext[par_index: OleVariant; const par_context: IXMLDOMNode]: IAttachment readonly dispid 1610743810;
    property _NewEnum: IUnknown readonly dispid -4;
  end;

// *********************************************************************//
// Interface: IAttachment
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {A2C40FB2-B768-4EC8-809A-6ECB4B89C6A7}
// *********************************************************************//
  IAttachment = interface(IDispatch)
    ['{A2C40FB2-B768-4EC8-809A-6ECB4B89C6A7}']
    function  Get_Property_(const par_name: WideString): OleVariant; safecall;
    procedure Set_Property_(const par_name: WideString; par_value: OleVariant); safecall;
    property Property_[const par_name: WideString]: OleVariant read Get_Property_;
  end;

// *********************************************************************//
// DispIntf:  IAttachmentDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {A2C40FB2-B768-4EC8-809A-6ECB4B89C6A7}
// *********************************************************************//
  IAttachmentDisp = dispinterface
    ['{A2C40FB2-B768-4EC8-809A-6ECB4B89C6A7}']
    property Property_[const par_name: WideString]: OleVariant readonly dispid 1610743808;
  end;

// *********************************************************************//
// Interface: IReceivedAttachment
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {C0C9F1C0-0039-427B-8ACC-AD172FE557A8}
// *********************************************************************//
  IReceivedAttachment = interface(IAttachment)
    ['{C0C9F1C0-0039-427B-8ACC-AD172FE557A8}']
    procedure SaveToFile(const par_name: WideString; par_override: WordBool); safecall;
    function  GetAsByteArray: OleVariant; safecall;
    function  GetAsString(const par_ContentCharacterSet: WideString): WideString; safecall;
  end;

// *********************************************************************//
// DispIntf:  IReceivedAttachmentDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {C0C9F1C0-0039-427B-8ACC-AD172FE557A8}
// *********************************************************************//
  IReceivedAttachmentDisp = dispinterface
    ['{C0C9F1C0-0039-427B-8ACC-AD172FE557A8}']
    procedure SaveToFile(const par_name: WideString; par_override: WordBool); dispid 1610809344;
    function  GetAsByteArray: OleVariant; dispid 1610809345;
    function  GetAsString(const par_ContentCharacterSet: WideString): WideString; dispid 1610809346;
    property Property_[const par_name: WideString]: OleVariant readonly dispid 1610743808;
  end;

// *********************************************************************//
// Interface: ISoapMapper
// Flags:     (256) OleAutomation
// GUID:      {C1E6061A-F8DC-4CA8-A952-FAF7419F1029}
// *********************************************************************//
  ISoapMapper = interface(IUnknown)
    ['{C1E6061A-F8DC-4CA8-A952-FAF7419F1029}']
    function  Get_ElementName(out par_ElementName: WideString): HResult; stdcall;
    function  Get_PartName(out par_PartName: WideString): HResult; stdcall;
    function  Get_ElementType(out par_ElementType: WideString): HResult; stdcall;
    function  Get_IsInput(out par_Input: smIsInputEnum): HResult; stdcall;
    function  Get_ComValue(out par_VarOut: OleVariant): HResult; stdcall;
    function  Set_ComValue(par_VarOut: OleVariant): HResult; stdcall;
    function  Get_CallIndex(out par_CallIndex: Integer): HResult; stdcall;
    function  Get_ParameterOrder(out par_paraOrder: Integer): HResult; stdcall;
    function  Get_XmlNamespace(out par_xmlNameSpace: WideString): HResult; stdcall;
    function  Get_VariantType(out par_Type: Integer): HResult; stdcall;
    function  Get_XsdType(out par_Type: enXSDType): HResult; stdcall;
    function  Get_SpecialType(out par_SpecialType: enSpecialType): HResult; stdcall;
    function  Save(const par_ISoapSerializer: ISoapSerializer; const par_encoding: WideString; 
                   par_enSaveStyle: enEncodingStyle; const par_MessageNamespace: WideString; 
                   par_flags: Integer): HResult; stdcall;
    function  Load(const par_ISoapReader: ISoapReader; const par_Node: IXMLDOMNode; 
                   const par_encoding: WideString; par_enStyle: enEncodingStyle; 
                   const par_MessageNamespace: WideString; par_flags: Integer): HResult; stdcall;
    function  Get_SchemaNode(out par_TypeNode: IXMLDOMNode): HResult; stdcall;
    function  Get_SchemaNamespace(out par_Namespace: WideString): HResult; stdcall;
    function  Set_PartName(const par_PartName: WideString): HResult; stdcall;
    function  Set_SpecialType(par_SpecialType: enSpecialType): HResult; stdcall;
    function  Set_CallIndex(par_CallIndex: Integer): HResult; stdcall;
  end;

// *********************************************************************//
// Interface: ISoapSerializer
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {23BDF2B5-2304-4550-BBE2-F197E2CC47B6}
// *********************************************************************//
  ISoapSerializer = interface(IDispatch)
    ['{23BDF2B5-2304-4550-BBE2-F197E2CC47B6}']
    procedure Init(par_output: OleVariant); safecall;
    procedure InitWithComposer(par_output: OleVariant; const par_composer: IMessageComposer); safecall;
    procedure StartEnvelope(const par_Prefix: WideString; const par_enc_style_uri: WideString; 
                            const par_encoding: WideString); safecall;
    procedure EndEnvelope; safecall;
    procedure StartHeader(const par_enc_style_uri: WideString); safecall;
    procedure StartHeaderElement(const par_name: WideString; const par_ns_uri: WideString; 
                                 par_mustUnderstand: SYSINT; const par_actor_uri: WideString; 
                                 const par_enc_style_uri: WideString; const par_Prefix: WideString); safecall;
    procedure EndHeaderElement; safecall;
    procedure EndHeader; safecall;
    procedure StartBody(const par_enc_style_uri: WideString); safecall;
    procedure EndBody; safecall;
    procedure StartElement(const par_name: WideString; const par_ns_uri: WideString; 
                           const par_enc_style_uri: WideString; const par_Prefix: WideString); safecall;
    procedure EndElement; safecall;
    procedure SoapAttribute(const par_name: WideString; const par_ns_uri: WideString; 
                            const par_value: WideString; const par_Prefix: WideString); safecall;
    procedure SoapNamespace(const par_Prefix: WideString; const par_ns_uri: WideString); safecall;
    procedure SoapDefaultNamespace(const par_ns_uri: WideString); safecall;
    procedure WriteString(const par_string: WideString); safecall;
    procedure WriteBuffer(par_len: Integer; var par_buffer: Byte); safecall;
    procedure StartFault(const par_FaultCode: WideString; const par_FaultString: WideString; 
                         const par_FaultActor: WideString; const par_FaultCodeNS: WideString); safecall;
    procedure StartFaultDetail(const par_enc_style_uri: WideString); safecall;
    procedure EndFaultDetail; safecall;
    procedure EndFault; safecall;
    procedure Reset; safecall;
    procedure WriteXml(const par_string: WideString); safecall;
    function  GetPrefixForNamespace(const par_ns_string: WideString): WideString; safecall;
    procedure EndHrefedElement; safecall;
    function  StartHrefedElement(const par_name: WideString; const par_ns_uri: WideString; 
                                 const par_enc_style_uri: WideString; const par_Prefix: WideString; 
                                 par_location: enElementLocation; const par_hrefidinput: WideString): WideString; safecall;
    function  Get_SoapFault: WordBool; safecall;
    function  GetContextItem(const par_key: WideString): OleVariant; safecall;
    procedure SetContextItem(const par_key: WideString; par_value: OleVariant); safecall;
    procedure AddAttachment(const par_att: IReceivedAttachment); safecall;
    procedure AddAttachmentAndReference(const par_att: IReceivedAttachment); safecall;
    procedure Finished; safecall;
    function  Get_Composer: IMessageComposer; safecall;
    function  CreateHRefId: WideString; safecall;
    property SoapFault: WordBool read Get_SoapFault;
    property Composer: IMessageComposer read Get_Composer;
  end;

// *********************************************************************//
// DispIntf:  ISoapSerializerDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {23BDF2B5-2304-4550-BBE2-F197E2CC47B6}
// *********************************************************************//
  ISoapSerializerDisp = dispinterface
    ['{23BDF2B5-2304-4550-BBE2-F197E2CC47B6}']
    procedure Init(par_output: OleVariant); dispid 1;
    procedure InitWithComposer(par_output: OleVariant; const par_composer: IMessageComposer); dispid 2;
    procedure StartEnvelope(const par_Prefix: WideString; const par_enc_style_uri: WideString; 
                            const par_encoding: WideString); dispid 3;
    procedure EndEnvelope; dispid 4;
    procedure StartHeader(const par_enc_style_uri: WideString); dispid 5;
    procedure StartHeaderElement(const par_name: WideString; const par_ns_uri: WideString; 
                                 par_mustUnderstand: SYSINT; const par_actor_uri: WideString; 
                                 const par_enc_style_uri: WideString; const par_Prefix: WideString); dispid 6;
    procedure EndHeaderElement; dispid 7;
    procedure EndHeader; dispid 8;
    procedure StartBody(const par_enc_style_uri: WideString); dispid 9;
    procedure EndBody; dispid 10;
    procedure StartElement(const par_name: WideString; const par_ns_uri: WideString; 
                           const par_enc_style_uri: WideString; const par_Prefix: WideString); dispid 11;
    procedure EndElement; dispid 12;
    procedure SoapAttribute(const par_name: WideString; const par_ns_uri: WideString; 
                            const par_value: WideString; const par_Prefix: WideString); dispid 13;
    procedure SoapNamespace(const par_Prefix: WideString; const par_ns_uri: WideString); dispid 14;
    procedure SoapDefaultNamespace(const par_ns_uri: WideString); dispid 15;
    procedure WriteString(const par_string: WideString); dispid 16;
    procedure WriteBuffer(par_len: Integer; var par_buffer: Byte); dispid 17;
    procedure StartFault(const par_FaultCode: WideString; const par_FaultString: WideString; 
                         const par_FaultActor: WideString; const par_FaultCodeNS: WideString); dispid 18;
    procedure StartFaultDetail(const par_enc_style_uri: WideString); dispid 19;
    procedure EndFaultDetail; dispid 20;
    procedure EndFault; dispid 21;
    procedure Reset; dispid 22;
    procedure WriteXml(const par_string: WideString); dispid 23;
    function  GetPrefixForNamespace(const par_ns_string: WideString): WideString; dispid 24;
    procedure EndHrefedElement; dispid 26;
    function  StartHrefedElement(const par_name: WideString; const par_ns_uri: WideString; 
                                 const par_enc_style_uri: WideString; const par_Prefix: WideString; 
                                 par_location: enElementLocation; const par_hrefidinput: WideString): WideString; dispid 25;
    property SoapFault: WordBool readonly dispid 1610743834;
    function  GetContextItem(const par_key: WideString): OleVariant; dispid 1610743835;
    procedure SetContextItem(const par_key: WideString; par_value: OleVariant); dispid 1610743836;
    procedure AddAttachment(const par_att: IReceivedAttachment); dispid 1610743837;
    procedure AddAttachmentAndReference(const par_att: IReceivedAttachment); dispid 1610743838;
    procedure Finished; dispid 1610743839;
    property Composer: IMessageComposer readonly dispid 1610743840;
    function  CreateHRefId: WideString; dispid 27;
  end;

// *********************************************************************//
// Interface: IMessageComposer
// Flags:     (256) OleAutomation
// GUID:      {906A72B9-FF88-4A49-AFA2-CC4CAB5104EC}
// *********************************************************************//
  IMessageComposer = interface(IUnknown)
    ['{906A72B9-FF88-4A49-AFA2-CC4CAB5104EC}']
    function  StartComposing(const par_destination: IComposerDestination): HResult; stdcall;
    function  EndComposing: HResult; stdcall;
    function  StartEnvelope(const par_charSet: WideString; out par_envelope: ISequentialStream): HResult; stdcall;
    function  EndEnvelope: HResult; stdcall;
    function  AddAttachment(const par_att: IReceivedAttachment; out par_reference: WideString): HResult; stdcall;
    function  SaveSpecialTypeMapper(const par_ISoapMapper: ISoapMapper; 
                                    const par_ISoapSerializer: ISoapSerializer): HResult; stdcall;
  end;

// *********************************************************************//
// Interface: IComposerDestination
// Flags:     (272) Hidden OleAutomation
// GUID:      {8E62C4B1-EE0C-48FB-9161-3EE041A03153}
// *********************************************************************//
  IComposerDestination = interface(IUnknown)
    ['{8E62C4B1-EE0C-48FB-9161-3EE041A03153}']
    function  Set_TotalSize(Param1: Integer): HResult; stdcall;
    function  Get_Property_(const par_name: WideString; out par_value: OleVariant): HResult; stdcall;
    function  Set_Property_(const par_name: WideString; par_value: OleVariant): HResult; stdcall;
    function  BeginSending(out par_stream: ISequentialStream; 
                           out par_flags: ComposerDestinationFlags): HResult; stdcall;
    function  EndSending: HResult; stdcall;
  end;

// *********************************************************************//
// Interface: IDataEncoder
// Flags:     (320) Dual OleAutomation
// GUID:      {663EB158-8D95-4657-AE32-B7C60DE6122F}
// *********************************************************************//
  IDataEncoder = interface(IUnknown)
    ['{663EB158-8D95-4657-AE32-B7C60DE6122F}']
    function  Get_Encoding: WideString; safecall;
    procedure SizeToEncode(var par_From: Pointer; par_FromSize: LongWord; out par_To: LongWord); safecall;
    procedure SizeToDecode(var par_From: Pointer; par_FromSize: LongWord; out par_To: LongWord); safecall;
    procedure Encode(var par_From: Pointer; par_FromSize: LongWord; out par_To: Pointer; 
                     var par_ToSize: LongWord); safecall;
    procedure Decode(var par_From: Pointer; par_FromSize: LongWord; out par_To: Pointer; 
                     var par_ToSize: LongWord); safecall;
    procedure SizeToEncodeStream(const par_From: IStream; out par_To: LongWord); safecall;
    procedure SizeToDecodeStream(const par_From: IStream; out par_To: LongWord); safecall;
    procedure EncodeStream(const par_Form: IStream; const par_To: IStream); safecall;
    procedure DecodeStream(const par_From: IStream; const par_To: IStream); safecall;
    property Encoding: WideString read Get_Encoding;
  end;

// *********************************************************************//
// DispIntf:  IDataEncoderDisp
// Flags:     (320) Dual OleAutomation
// GUID:      {663EB158-8D95-4657-AE32-B7C60DE6122F}
// *********************************************************************//
  IDataEncoderDisp = dispinterface
    ['{663EB158-8D95-4657-AE32-B7C60DE6122F}']
    property Encoding: WideString readonly dispid 1610678272;
    procedure SizeToEncode(var par_From: {??Pointer}OleVariant; par_FromSize: LongWord; 
                           out par_To: LongWord); dispid 1610678273;
    procedure SizeToDecode(var par_From: {??Pointer}OleVariant; par_FromSize: LongWord; 
                           out par_To: LongWord); dispid 1610678274;
    procedure Encode(var par_From: {??Pointer}OleVariant; par_FromSize: LongWord; 
                     out par_To: {??Pointer}OleVariant; var par_ToSize: LongWord); dispid 1610678275;
    procedure Decode(var par_From: {??Pointer}OleVariant; par_FromSize: LongWord; 
                     out par_To: {??Pointer}OleVariant; var par_ToSize: LongWord); dispid 1610678276;
    procedure SizeToEncodeStream(const par_From: IStream; out par_To: LongWord); dispid 1610678277;
    procedure SizeToDecodeStream(const par_From: IStream; out par_To: LongWord); dispid 1610678278;
    procedure EncodeStream(const par_Form: IStream; const par_To: IStream); dispid 1610678279;
    procedure DecodeStream(const par_From: IStream; const par_To: IStream); dispid 1610678280;
  end;

// *********************************************************************//
// Interface: IStream
// Flags:     (0)
// GUID:      {0000000C-0000-0000-C000-000000000046}
// *********************************************************************//
  IStream = interface(ISequentialStream)
    ['{0000000C-0000-0000-C000-000000000046}']
    function  RemoteSeek(dlibMove: _LARGE_INTEGER; dwOrigin: LongWord; 
                         out plibNewPosition: _ULARGE_INTEGER): HResult; stdcall;
    function  SetSize(libNewSize: _ULARGE_INTEGER): HResult; stdcall;
    function  RemoteCopyTo(const pstm: IStream; cb: _ULARGE_INTEGER; out pcbRead: _ULARGE_INTEGER; 
                           out pcbWritten: _ULARGE_INTEGER): HResult; stdcall;
    function  Commit(grfCommitFlags: LongWord): HResult; stdcall;
    function  Revert: HResult; stdcall;
    function  LockRegion(libOffset: _ULARGE_INTEGER; cb: _ULARGE_INTEGER; dwLockType: LongWord): HResult; stdcall;
    function  UnlockRegion(libOffset: _ULARGE_INTEGER; cb: _ULARGE_INTEGER; dwLockType: LongWord): HResult; stdcall;
    function  Stat(out pstatstg: tagSTATSTG; grfStatFlag: LongWord): HResult; stdcall;
    function  Clone(out ppstm: IStream): HResult; stdcall;
  end;

// *********************************************************************//
// Interface: IDataEncoderFactory
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {456C5AB4-2A2A-4289-9D4C-0C28BF739EE4}
// *********************************************************************//
  IDataEncoderFactory = interface(IDispatch)
    ['{456C5AB4-2A2A-4289-9D4C-0C28BF739EE4}']
    procedure AddDataEncoder(const par_encoding: WideString; const par_encoder: IDataEncoder); safecall;
    function  GetDataEncoder(const par_encoding: WideString): IDataEncoder; safecall;
  end;

// *********************************************************************//
// DispIntf:  IDataEncoderFactoryDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {456C5AB4-2A2A-4289-9D4C-0C28BF739EE4}
// *********************************************************************//
  IDataEncoderFactoryDisp = dispinterface
    ['{456C5AB4-2A2A-4289-9D4C-0C28BF739EE4}']
    procedure AddDataEncoder(const par_encoding: WideString; const par_encoder: IDataEncoder); dispid 1610743808;
    function  GetDataEncoder(const par_encoding: WideString): IDataEncoder; dispid 1610743809;
  end;

// *********************************************************************//
// Interface: IFileAttachment
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {D6DEA9EB-28EA-45C7-A46A-72D26668C1EA}
// *********************************************************************//
  IFileAttachment = interface(IAttachment)
    ['{D6DEA9EB-28EA-45C7-A46A-72D26668C1EA}']
    function  Get_FileName: WideString; safecall;
    procedure Set_FileName(const par_value: WideString); safecall;
    procedure Set_DeleteAfterSending(par_value: WordBool); safecall;
    function  Get_DeleteAfterSending: WordBool; safecall;
    property FileName: WideString read Get_FileName;
    property DeleteAfterSending: WordBool write Set_DeleteAfterSending;
  end;

// *********************************************************************//
// DispIntf:  IFileAttachmentDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {D6DEA9EB-28EA-45C7-A46A-72D26668C1EA}
// *********************************************************************//
  IFileAttachmentDisp = dispinterface
    ['{D6DEA9EB-28EA-45C7-A46A-72D26668C1EA}']
    property FileName: WideString readonly dispid 1610809344;
    property DeleteAfterSending: WordBool writeonly dispid 1610809346;
    property Property_[const par_name: WideString]: OleVariant readonly dispid 1610743808;
  end;

// *********************************************************************//
// Interface: IStringAttachment
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {8004A743-6A1E-45E4-B2E2-A6D117F06008}
// *********************************************************************//
  IStringAttachment = interface(IAttachment)
    ['{8004A743-6A1E-45E4-B2E2-A6D117F06008}']
    function  Get_String_: WideString; safecall;
    procedure Set_String_(const par_value: WideString); safecall;
    function  Get_ContentCharacterSet: WideString; safecall;
    procedure Set_ContentCharacterSet(const par_value: WideString); safecall;
    property String_: WideString read Get_String_;
    property ContentCharacterSet: WideString read Get_ContentCharacterSet;
  end;

// *********************************************************************//
// DispIntf:  IStringAttachmentDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {8004A743-6A1E-45E4-B2E2-A6D117F06008}
// *********************************************************************//
  IStringAttachmentDisp = dispinterface
    ['{8004A743-6A1E-45E4-B2E2-A6D117F06008}']
    property String_: WideString readonly dispid 1610809344;
    property ContentCharacterSet: WideString readonly dispid 1610809346;
    property Property_[const par_name: WideString]: OleVariant readonly dispid 1610743808;
  end;

// *********************************************************************//
// Interface: IByteArrayAttachment
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {52088645-8E96-4C18-8621-B46611635303}
// *********************************************************************//
  IByteArrayAttachment = interface(IAttachment)
    ['{52088645-8E96-4C18-8621-B46611635303}']
    function  Get_Array_: OleVariant; safecall;
    procedure Set_Array_(par_value: OleVariant); safecall;
    property Array_: OleVariant read Get_Array_;
  end;

// *********************************************************************//
// DispIntf:  IByteArrayAttachmentDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {52088645-8E96-4C18-8621-B46611635303}
// *********************************************************************//
  IByteArrayAttachmentDisp = dispinterface
    ['{52088645-8E96-4C18-8621-B46611635303}']
    property Array_: OleVariant readonly dispid 1610809344;
    property Property_[const par_name: WideString]: OleVariant readonly dispid 1610743808;
  end;

// *********************************************************************//
// Interface: IStreamAttachment
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {BE1DBCF5-2260-470A-8E1C-E2406D106E0A}
// *********************************************************************//
  IStreamAttachment = interface(IAttachment)
    ['{BE1DBCF5-2260-470A-8E1C-E2406D106E0A}']
    function  Get_Stream: IStream; safecall;
    procedure _Set_Stream(const par_value: IStream); safecall;
    property Stream: IStream read Get_Stream;
  end;

// *********************************************************************//
// DispIntf:  IStreamAttachmentDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {BE1DBCF5-2260-470A-8E1C-E2406D106E0A}
// *********************************************************************//
  IStreamAttachmentDisp = dispinterface
    ['{BE1DBCF5-2260-470A-8E1C-E2406D106E0A}']
    property Stream: IStream readonly dispid 1610809344;
    property Property_[const par_name: WideString]: OleVariant readonly dispid 1610743808;
  end;

// *********************************************************************//
// Interface: ISentAttachments
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {95A098C0-EB61-4895-91C7-78873251322E}
// *********************************************************************//
  ISentAttachments = interface(IDispatch)
    ['{95A098C0-EB61-4895-91C7-78873251322E}']
    function  Get_Count: Integer; safecall;
    function  Get_Item(par_index: Integer): IReceivedAttachment; safecall;
    procedure Add(const par_att: IReceivedAttachment); safecall;
    property Count: Integer read Get_Count;
    property Item[par_index: Integer]: IReceivedAttachment read Get_Item; default;
  end;

// *********************************************************************//
// DispIntf:  ISentAttachmentsDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {95A098C0-EB61-4895-91C7-78873251322E}
// *********************************************************************//
  ISentAttachmentsDisp = dispinterface
    ['{95A098C0-EB61-4895-91C7-78873251322E}']
    property Count: Integer readonly dispid 1610743808;
    property Item[par_index: Integer]: IReceivedAttachment readonly dispid 0; default;
    procedure Add(const par_att: IReceivedAttachment); dispid 1610743810;
  end;

// *********************************************************************//
// Interface: IGetComposerDestination
// Flags:     (272) Hidden OleAutomation
// GUID:      {9E6CDFEF-4C42-411B-BACA-FE96F7A13C04}
// *********************************************************************//
  IGetComposerDestination = interface(IUnknown)
    ['{9E6CDFEF-4C42-411B-BACA-FE96F7A13C04}']
    function  Get_ComposerDestination(out par_value: IComposerDestination): HResult; stdcall;
  end;

// *********************************************************************//
// Interface: IDimeComposer
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {ABAADE34-EEF6-408A-8896-65BE669D27FA}
// *********************************************************************//
  IDimeComposer = interface(IDispatch)
    ['{ABAADE34-EEF6-408A-8896-65BE669D27FA}']
    procedure Initialize(const par_tempFolder: WideString; par_maxSize: Integer; 
                         par_chunkSize: Integer); safecall;
  end;

// *********************************************************************//
// DispIntf:  IDimeComposerDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {ABAADE34-EEF6-408A-8896-65BE669D27FA}
// *********************************************************************//
  IDimeComposerDisp = dispinterface
    ['{ABAADE34-EEF6-408A-8896-65BE669D27FA}']
    procedure Initialize(const par_tempFolder: WideString; par_maxSize: Integer; 
                         par_chunkSize: Integer); dispid 1610743808;
  end;

// *********************************************************************//
// Interface: ISimpleComposer
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {70824404-7A18-412A-9A83-A9EC0F3FF045}
// *********************************************************************//
  ISimpleComposer = interface(IDispatch)
    ['{70824404-7A18-412A-9A83-A9EC0F3FF045}']
  end;

// *********************************************************************//
// DispIntf:  ISimpleComposerDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {70824404-7A18-412A-9A83-A9EC0F3FF045}
// *********************************************************************//
  ISimpleComposerDisp = dispinterface
    ['{70824404-7A18-412A-9A83-A9EC0F3FF045}']
  end;

// *********************************************************************//
// Interface: IGetParserSource
// Flags:     (272) Hidden OleAutomation
// GUID:      {BB63287E-1407-40E3-89AB-38CB2746547F}
// *********************************************************************//
  IGetParserSource = interface(IUnknown)
    ['{BB63287E-1407-40E3-89AB-38CB2746547F}']
    function  Get_ParserSource(out par_value: IParserSource): HResult; stdcall;
  end;

// *********************************************************************//
// Interface: IDimeParser
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {E3F8BAA5-8A05-4641-91CE-3FBC533D1EDB}
// *********************************************************************//
  IDimeParser = interface(IDispatch)
    ['{E3F8BAA5-8A05-4641-91CE-3FBC533D1EDB}']
    procedure Initialize(const par_tempFolder: WideString; par_maxSize: Integer); safecall;
  end;

// *********************************************************************//
// DispIntf:  IDimeParserDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {E3F8BAA5-8A05-4641-91CE-3FBC533D1EDB}
// *********************************************************************//
  IDimeParserDisp = dispinterface
    ['{E3F8BAA5-8A05-4641-91CE-3FBC533D1EDB}']
    procedure Initialize(const par_tempFolder: WideString; par_maxSize: Integer); dispid 1610743808;
  end;

// *********************************************************************//
// Interface: ISimpleParser
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {B313A227-0798-4A87-9074-48CA2164D0F7}
// *********************************************************************//
  ISimpleParser = interface(IDispatch)
    ['{B313A227-0798-4A87-9074-48CA2164D0F7}']
  end;

// *********************************************************************//
// DispIntf:  ISimpleParserDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {B313A227-0798-4A87-9074-48CA2164D0F7}
// *********************************************************************//
  ISimpleParserDisp = dispinterface
    ['{B313A227-0798-4A87-9074-48CA2164D0F7}']
  end;

// *********************************************************************//
// Interface: ISoapClient
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {7F017F92-9257-11D5-87EA-00B0D0BE6479}
// *********************************************************************//
  ISoapClient = interface(IDispatch)
    ['{7F017F92-9257-11D5-87EA-00B0D0BE6479}']
    procedure MSSoapInit(const par_WSDLFile: WideString; const par_ServiceName: WideString; 
                         const par_Port: WideString; const par_WSMLFile: WideString); safecall;
    function  Get_FaultCode: WideString; safecall;
    function  Get_FaultString: WideString; safecall;
    function  Get_FaultActor: WideString; safecall;
    function  Get_Detail: WideString; safecall;
    function  Get_ClientProperty(const par_PropertyName: WideString): OleVariant; safecall;
    procedure _Set_HeaderHandler(const Param1: IDispatch); safecall;
    procedure Set_ClientProperty(const par_PropertyName: WideString; par_PropertyValue: OleVariant); safecall;
    function  Get_ConnectorProperty(const par_PropertyName: WideString): OleVariant; safecall;
    procedure Set_ConnectorProperty(const par_PropertyName: WideString; 
                                    par_PropertyValue: OleVariant); safecall;
    procedure MSSoapInit2(par_WSDLFile: OleVariant; par_WSMLFile: OleVariant; 
                          const par_ServiceName: WideString; const par_Port: WideString; 
                          const par_Namespace: WideString); safecall;
    function  Get_FaultCodeNamespace: WideString; safecall;
    procedure _Set_ClientProperty(const par_PropertyName: WideString; par_PropertyValue: OleVariant); safecall;
    property FaultCode: WideString read Get_FaultCode;
    property FaultString: WideString read Get_FaultString;
    property FaultActor: WideString read Get_FaultActor;
    property Detail: WideString read Get_Detail;
    property ClientProperty[const par_PropertyName: WideString]: OleVariant read Get_ClientProperty;
    property ConnectorProperty[const par_PropertyName: WideString]: OleVariant read Get_ConnectorProperty;
    property FaultCodeNamespace: WideString read Get_FaultCodeNamespace;
  end;

// *********************************************************************//
// DispIntf:  ISoapClientDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {7F017F92-9257-11D5-87EA-00B0D0BE6479}
// *********************************************************************//
  ISoapClientDisp = dispinterface
    ['{7F017F92-9257-11D5-87EA-00B0D0BE6479}']
    procedure MSSoapInit(const par_WSDLFile: WideString; const par_ServiceName: WideString; 
                         const par_Port: WideString; const par_WSMLFile: WideString); dispid 1;
    property FaultCode: WideString readonly dispid 2;
    property FaultString: WideString readonly dispid 3;
    property FaultActor: WideString readonly dispid 4;
    property Detail: WideString readonly dispid 5;
    property ClientProperty[const par_PropertyName: WideString]: OleVariant readonly dispid 1610743813;
    property ConnectorProperty[const par_PropertyName: WideString]: OleVariant readonly dispid 1610743816;
    procedure MSSoapInit2(par_WSDLFile: OleVariant; par_WSMLFile: OleVariant; 
                          const par_ServiceName: WideString; const par_Port: WideString; 
                          const par_Namespace: WideString); dispid 7;
    property FaultCodeNamespace: WideString readonly dispid 6;
  end;

// *********************************************************************//
// Interface: ISoapServer
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {7F017F93-9257-11D5-87EA-00B0D0BE6479}
// *********************************************************************//
  ISoapServer = interface(IDispatch)
    ['{7F017F93-9257-11D5-87EA-00B0D0BE6479}']
    procedure Init(const par_WSDLFile: WideString; const par_WSMLFile: WideString); safecall;
    procedure SoapInvoke(par_Input: OleVariant; const par_OutputStream: IUnknown; 
                         const par_soapAction: WideString); safecall;
    procedure SoapInvokeEx(par_Input: OleVariant; const par_OutputStream: IUnknown; 
                           const par_ServerObject: IUnknown; const par_soapAction: WideString; 
                           const par_ContentType: WideString); safecall;
    procedure Set_XmlVersion(const Param1: WideString); safecall;
  end;

// *********************************************************************//
// DispIntf:  ISoapServerDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {7F017F93-9257-11D5-87EA-00B0D0BE6479}
// *********************************************************************//
  ISoapServerDisp = dispinterface
    ['{7F017F93-9257-11D5-87EA-00B0D0BE6479}']
    procedure Init(const par_WSDLFile: WideString; const par_WSMLFile: WideString); dispid 1;
    procedure SoapInvoke(par_Input: OleVariant; const par_OutputStream: IUnknown; 
                         const par_soapAction: WideString); dispid 2;
    procedure SoapInvokeEx(par_Input: OleVariant; const par_OutputStream: IUnknown; 
                           const par_ServerObject: IUnknown; const par_soapAction: WideString; 
                           const par_ContentType: WideString); dispid 3;
    property XmlVersion: WideString writeonly dispid 4;
  end;

// *********************************************************************//
// Interface: ISoapTypeMapperFactory
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {FCED9F15-D0A7-4380-87E6-992381ACD213}
// *********************************************************************//
  ISoapTypeMapperFactory = interface(IDispatch)
    ['{FCED9F15-D0A7-4380-87E6-992381ACD213}']
    procedure AddSchema(const par_SchemaNode: IXMLDOMNode); safecall;
    function  GetElementMapperByName(const par_ElementName: WideString; 
                                     const par_ElementNamespace: WideString): ISoapTypeMapper; safecall;
    function  GetTypeMapperByName(const par_TypeName: WideString; 
                                  const par_TypeNamespace: WideString): ISoapTypeMapper; safecall;
    function  GetElementMapper(const par_ElementNode: IXMLDOMNode): ISoapTypeMapper; safecall;
    function  GetTypeMapper(const par_TypeNode: IXMLDOMNode): ISoapTypeMapper; safecall;
    procedure AddType(const par_TypeName: WideString; const par_TypeNamespace: WideString; 
                      const par_ProgID: WideString; const par_IID: WideString); safecall;
    procedure AddElement(const par_ElementName: WideString; const par_ElementNamespace: WideString; 
                         const par_ProgID: WideString; const par_IID: WideString); safecall;
    function  GetMapper(par_xsdType: enXSDType; const par_SchemaNode: IXMLDOMNode): ISoapTypeMapper; safecall;
    procedure AddCustomMapper(const par_ProgID: WideString; const par_WSMLNode: IXMLDOMNode); safecall;
    function  GetDefinitionsNode(const par_BaseName: WideString; const par_Namespace: WideString; 
                                 par_LookForElement: WordBool): IXMLDOMNode; safecall;
  end;

// *********************************************************************//
// DispIntf:  ISoapTypeMapperFactoryDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {FCED9F15-D0A7-4380-87E6-992381ACD213}
// *********************************************************************//
  ISoapTypeMapperFactoryDisp = dispinterface
    ['{FCED9F15-D0A7-4380-87E6-992381ACD213}']
    procedure AddSchema(const par_SchemaNode: IXMLDOMNode); dispid 6;
    function  GetElementMapperByName(const par_ElementName: WideString; 
                                     const par_ElementNamespace: WideString): ISoapTypeMapper; dispid 1;
    function  GetTypeMapperByName(const par_TypeName: WideString; 
                                  const par_TypeNamespace: WideString): ISoapTypeMapper; dispid 2;
    function  GetElementMapper(const par_ElementNode: IXMLDOMNode): ISoapTypeMapper; dispid 7;
    function  GetTypeMapper(const par_TypeNode: IXMLDOMNode): ISoapTypeMapper; dispid 8;
    procedure AddType(const par_TypeName: WideString; const par_TypeNamespace: WideString; 
                      const par_ProgID: WideString; const par_IID: WideString); dispid 4;
    procedure AddElement(const par_ElementName: WideString; const par_ElementNamespace: WideString; 
                         const par_ProgID: WideString; const par_IID: WideString); dispid 5;
    function  GetMapper(par_xsdType: enXSDType; const par_SchemaNode: IXMLDOMNode): ISoapTypeMapper; dispid 3;
    procedure AddCustomMapper(const par_ProgID: WideString; const par_WSMLNode: IXMLDOMNode); dispid 9;
    function  GetDefinitionsNode(const par_BaseName: WideString; const par_Namespace: WideString; 
                                 par_LookForElement: WordBool): IXMLDOMNode; dispid 10;
  end;

// *********************************************************************//
// Interface: ISoapTypeMapper
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {29D3F736-1C25-44EE-9CEE-3F52F226BA8A}
// *********************************************************************//
  ISoapTypeMapper = interface(IDispatch)
    ['{29D3F736-1C25-44EE-9CEE-3F52F226BA8A}']
    procedure Init(const par_Factory: ISoapTypeMapperFactory; const par_Schema: IXMLDOMNode; 
                   const par_WSMLNode: IXMLDOMNode; par_xsdType: enXSDType); safecall;
    function  Read(const par_soapreader: ISoapReader; const par_Node: IXMLDOMNode; 
                   const par_encoding: WideString; par_encodingMode: enEncodingStyle; 
                   par_flags: Integer): OleVariant; safecall;
    procedure Write(const par_ISoapSerializer: ISoapSerializer; const par_encoding: WideString; 
                    par_encodingMode: enEncodingStyle; par_flags: Integer; var par_var: OleVariant); safecall;
    function  VarType: Integer; safecall;
    function  Iid: WideString; safecall;
    function  SchemaNode: IXMLDOMNode; safecall;
    function  XsdType: enXSDType; safecall;
  end;

// *********************************************************************//
// DispIntf:  ISoapTypeMapperDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {29D3F736-1C25-44EE-9CEE-3F52F226BA8A}
// *********************************************************************//
  ISoapTypeMapperDisp = dispinterface
    ['{29D3F736-1C25-44EE-9CEE-3F52F226BA8A}']
    procedure Init(const par_Factory: ISoapTypeMapperFactory; const par_Schema: IXMLDOMNode; 
                   const par_WSMLNode: IXMLDOMNode; par_xsdType: enXSDType); dispid 1;
    function  Read(const par_soapreader: ISoapReader; const par_Node: IXMLDOMNode; 
                   const par_encoding: WideString; par_encodingMode: enEncodingStyle; 
                   par_flags: Integer): OleVariant; dispid 2;
    procedure Write(const par_ISoapSerializer: ISoapSerializer; const par_encoding: WideString; 
                    par_encodingMode: enEncodingStyle; par_flags: Integer; var par_var: OleVariant); dispid 3;
    function  VarType: Integer; dispid 4;
    function  Iid: WideString; dispid 5;
    function  SchemaNode: IXMLDOMNode; dispid 6;
    function  XsdType: enXSDType; dispid 7;
  end;

// *********************************************************************//
// Interface: IHeaderHandler
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {504D4B91-76B8-4D88-95EA-CEB5E0FE41F3}
// *********************************************************************//
  IHeaderHandler = interface(IDispatch)
    ['{504D4B91-76B8-4D88-95EA-CEB5E0FE41F3}']
    function  WillWriteHeaders: WordBool; safecall;
    procedure WriteHeaders(const par_ISoapSerializer: ISoapSerializer; const par_Object: IDispatch); safecall;
    function  ReadHeader(const par_Reader: ISoapReader; const par_HeaderNode: IXMLDOMNode; 
                         const par_Object: IDispatch): WordBool; safecall;
  end;

// *********************************************************************//
// DispIntf:  IHeaderHandlerDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {504D4B91-76B8-4D88-95EA-CEB5E0FE41F3}
// *********************************************************************//
  IHeaderHandlerDisp = dispinterface
    ['{504D4B91-76B8-4D88-95EA-CEB5E0FE41F3}']
    function  WillWriteHeaders: WordBool; dispid 1;
    procedure WriteHeaders(const par_ISoapSerializer: ISoapSerializer; const par_Object: IDispatch); dispid 2;
    function  ReadHeader(const par_Reader: ISoapReader; const par_HeaderNode: IXMLDOMNode; 
                         const par_Object: IDispatch): WordBool; dispid 3;
  end;

// *********************************************************************//
// Interface: IEnumSoapMappers
// Flags:     (256) OleAutomation
// GUID:      {ACDDCED6-6DB8-497A-BF10-068711629924}
// *********************************************************************//
  IEnumSoapMappers = interface(IUnknown)
    ['{ACDDCED6-6DB8-497A-BF10-068711629924}']
    function  Next(par_celt: Integer; out par_soapmapper: ISoapMapper; out par_Fetched: Integer): HResult; stdcall;
    function  Skip(par_celt: Integer): HResult; stdcall;
    function  Reset: HResult; stdcall;
    function  Clone(out par_enum: IEnumSoapMappers): HResult; stdcall;
  end;

// *********************************************************************//
// Interface: IWSDLMessage
// Flags:     (256) OleAutomation
// GUID:      {49F9421C-DC88-43E1-825F-70E788E9A9A9}
// *********************************************************************//
  IWSDLMessage = interface(IUnknown)
    ['{49F9421C-DC88-43E1-825F-70E788E9A9A9}']
    function  Get_EncodingStyle(out par_enStyle: enEncodingStyle): HResult; stdcall;
    function  Get_EncodingNamespace(out par_encodingNamespace: WideString): HResult; stdcall;
    function  Get_MessageName(out par_messageName: WideString): HResult; stdcall;
    function  Get_MessageNamespace(out par_MessageNamespace: WideString): HResult; stdcall;
    function  Get_MessageParts(out par_IEnumSoapMappers: IEnumSoapMappers): HResult; stdcall;
    function  GetComposer(const par_tempFolder: WideString; par_maxSize: Integer; 
                          out par_composer: IMessageComposer): HResult; stdcall;
    function  GetParser(const par_tempFolder: WideString; par_maxSize: Integer; 
                        out par_parser: IMessageParser): HResult; stdcall;
    function  AddAttachmentCollection(const par_bstrPartName: WideString; 
                                      par_lserverSideCallIndex: Integer): HResult; stdcall;
  end;

// *********************************************************************//
// Interface: IWSDLOperation
// Flags:     (256) OleAutomation
// GUID:      {A0B762A7-9F3E-48D8-B333-770E5FA72A1E}
// *********************************************************************//
  IWSDLOperation = interface(IUnknown)
    ['{A0B762A7-9F3E-48D8-B333-770E5FA72A1E}']
    function  Get_Documentation(out par_Documentation: WideString): HResult; stdcall;
    function  Get_Name(out par_OperationName: WideString): HResult; stdcall;
    function  Get_SoapAction(out par_soapAction: WideString): HResult; stdcall;
    function  Get_ObjectProgId(out par_ObjectProgId: WideString): HResult; stdcall;
    function  Get_ObjectMethod(out par_ObjectMethod: WideString): HResult; stdcall;
    function  Get_InputMessage(out par_InputMessage: IWSDLMessage): HResult; stdcall;
    function  Get_OutputMessage(out par_OutputMessage: IWSDLMessage): HResult; stdcall;
    function  Get_PreferredEncoding(out par_preferredEncoding: WideString): HResult; stdcall;
    function  GetOperationParts(out par_IEnumSoapMappers: IEnumSoapMappers): HResult; stdcall;
    function  ExecuteOperation(const par_ISoapReader: ISoapReader; 
                               const par_ISoapSerializer: ISoapSerializer): HResult; stdcall;
    function  ExecuteOperationEx(const par_ISoapReader: ISoapReader; 
                                 const par_ISoapSerializer: ISoapSerializer; 
                                 const par_ServerObject: IUnknown): HResult; stdcall;
    function  Save(const par_ISoapSerializer: ISoapSerializer; par_Input: WordBool): HResult; stdcall;
    function  Load(const par_ISoapReader: ISoapReader; par_Input: WordBool): HResult; stdcall;
    function  GetNameRef: PWord1; stdcall;
    function  Get_type_(out par_Type: enOperationType): HResult; stdcall;
  end;

// *********************************************************************//
// Interface: IEnumWSDLOperations
// Flags:     (256) OleAutomation
// GUID:      {B0BBA669-55F7-4E9C-941E-49BC4715C834}
// *********************************************************************//
  IEnumWSDLOperations = interface(IUnknown)
    ['{B0BBA669-55F7-4E9C-941E-49BC4715C834}']
    function  Next(par_celt: Integer; out par_WSDLOperation: IWSDLOperation; 
                   out par_Fetched: Integer): HResult; stdcall;
    function  Skip(par_celt: Integer): HResult; stdcall;
    function  Reset: HResult; stdcall;
    function  Clone(out par_enum: IEnumWSDLOperations): HResult; stdcall;
    function  Find(const par_OperationToFind: WideString; out par_IWSDLOperation: IWSDLOperation): HResult; stdcall;
    function  Size(out par_Size: Integer): HResult; stdcall;
  end;

// *********************************************************************//
// Interface: IWSDLPort
// Flags:     (256) OleAutomation
// GUID:      {4D40B730-F5FA-472C-8819-DDCD183BD0DE}
// *********************************************************************//
  IWSDLPort = interface(IUnknown)
    ['{4D40B730-F5FA-472C-8819-DDCD183BD0DE}']
    function  Get_Name(out par_PortName: WideString): HResult; stdcall;
    function  Get_Address(out par_PortAddress: WideString): HResult; stdcall;
    function  Get_BindStyle(out par_BindStyle: WideString): HResult; stdcall;
    function  Get_Transport(out par_Transport: WideString): HResult; stdcall;
    function  Get_Documentation(out par_Documentation: WideString): HResult; stdcall;
    function  GetSoapOperations(out par_IWSDLOperations: IEnumWSDLOperations): HResult; stdcall;
  end;

// *********************************************************************//
// Interface: IEnumWSDLPorts
// Flags:     (256) OleAutomation
// GUID:      {EC189C1C-31B3-4193-BDCA-98EC44FF3EE0}
// *********************************************************************//
  IEnumWSDLPorts = interface(IUnknown)
    ['{EC189C1C-31B3-4193-BDCA-98EC44FF3EE0}']
    function  Next(par_celt: Integer; out WSDLPort: IWSDLPort; var par_Fetched: Integer): HResult; stdcall;
    function  Skip(par_celt: Integer): HResult; stdcall;
    function  Reset: HResult; stdcall;
    function  Clone(out par_enum: IEnumWSDLPorts): HResult; stdcall;
    function  Find(const par_PortToFind: WideString; out par_IWSDLPort: IWSDLPort): HResult; stdcall;
  end;

// *********************************************************************//
// Interface: IWSDLService
// Flags:     (256) OleAutomation
// GUID:      {9B5D8D63-EA54-41F6-9F12-F77A13111EC6}
// *********************************************************************//
  IWSDLService = interface(IUnknown)
    ['{9B5D8D63-EA54-41F6-9F12-F77A13111EC6}']
    function  Get_Name(out par_ServiceName: WideString): HResult; stdcall;
    function  Get_Documentation(out par_Documentation: WideString): HResult; stdcall;
    function  GetSoapPorts(out par_IWSDLPorts: IEnumWSDLPorts): HResult; stdcall;
  end;

// *********************************************************************//
// Interface: IEnumWSDLService
// Flags:     (256) OleAutomation
// GUID:      {104F6816-093E-41D7-A68B-8E1CC408B279}
// *********************************************************************//
  IEnumWSDLService = interface(IUnknown)
    ['{104F6816-093E-41D7-A68B-8E1CC408B279}']
    function  Next(par_celt: Integer; out par_IWSDLService: IWSDLService; var par_Fetched: Integer): HResult; stdcall;
    function  Skip(par_celt: Integer): HResult; stdcall;
    function  Reset: HResult; stdcall;
    function  Clone(out par_enum: IEnumWSDLService): HResult; stdcall;
    function  Find(const par_ServiceToFind: WideString; out par_WSDLService: IWSDLService): HResult; stdcall;
  end;

// *********************************************************************//
// Interface: IWSDLReader
// Flags:     (256) OleAutomation
// GUID:      {DE523FD4-AFB8-4643-BA90-9DEB3C7FB4A3}
// *********************************************************************//
  IWSDLReader = interface(IUnknown)
    ['{DE523FD4-AFB8-4643-BA90-9DEB3C7FB4A3}']
    function  Load(const par_WSDLFile: WideString; const par_WSMLFile: WideString): HResult; stdcall;
    function  Load2(par_WSDLFile: OleVariant; par_WSMLFile: OleVariant; 
                    const par_StartingNamespace: WideString): HResult; stdcall;
    function  GetSoapServices(out par_IWSDLServiceEnum: IEnumWSDLService): HResult; stdcall;
    function  ParseRequest(const par_ISoapReader: ISoapReader; out par_IWSDLPort: IWSDLPort; 
                           out par_IWSDLOperation: IWSDLOperation): HResult; stdcall;
    function  SetProperty(const par_PropertyName: WideString; par_PropValue: OleVariant): HResult; stdcall;
    function  Get_TypeFactory(out par_Factory: ISoapTypeMapperFactory): HResult; stdcall;
  end;

// *********************************************************************//
// Interface: IWSDLBinding
// Flags:     (272) Hidden OleAutomation
// GUID:      {AB0E0268-304D-43FC-8603-B1105F3A7512}
// *********************************************************************//
  IWSDLBinding = interface(IUnknown)
    ['{AB0E0268-304D-43FC-8603-B1105F3A7512}']
    function  Initialize(const pWSMLBindingNode: IXMLDOMNode; var pbstrNamespace: WideString): HResult; stdcall;
    function  ParseBinding(const pWSDLInputOutputNode: IXMLDOMNode; var ppSoapBodyNode: IXMLDOMNode): HResult; stdcall;
    function  ApplyBinding(const pWSDLMessage: IWSDLMessage; 
                           const pWSDLInputOutputNode: IXMLDOMNode; 
                           const pWSMLOperationNode: IXMLDOMNode): HResult; stdcall;
    function  GetComposer(const bstrTemporaryAttachmentFolder: WideString; 
                          lMaxAttachmentSize: Integer; lReserved: Integer; 
                          var ppComposer: IMessageComposer): HResult; stdcall;
    function  GetParser(const bstrTemporaryAttachmentFolder: WideString; 
                        lMaxAttachmentSize: Integer; var ppParser: IMessageParser): HResult; stdcall;
  end;

// *********************************************************************//
// Interface: ISoapConnector
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {0AF40C4E-9257-11D5-87EA-00B0D0BE6479}
// *********************************************************************//
  ISoapConnector = interface(IDispatch)
    ['{0AF40C4E-9257-11D5-87EA-00B0D0BE6479}']
    function  Get_InputStream: IStream; safecall;
    function  Get_OutputStream: IStream; safecall;
    function  Get_Property_(const par_name: WideString): OleVariant; safecall;
    procedure Set_Property_(const par_name: WideString; par_value: OleVariant); safecall;
    procedure ConnectWSDL(const par_Port: IWSDLPort); safecall;
    procedure BeginMessageWSDL(const par_operation: IWSDLOperation); safecall;
    procedure EndMessage; safecall;
    procedure Reset; safecall;
    procedure Connect; safecall;
    procedure BeginMessage; safecall;
    property InputStream: IStream read Get_InputStream;
    property OutputStream: IStream read Get_OutputStream;
    property Property_[const par_name: WideString]: OleVariant read Get_Property_ write Set_Property_;
  end;

// *********************************************************************//
// DispIntf:  ISoapConnectorDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {0AF40C4E-9257-11D5-87EA-00B0D0BE6479}
// *********************************************************************//
  ISoapConnectorDisp = dispinterface
    ['{0AF40C4E-9257-11D5-87EA-00B0D0BE6479}']
    property InputStream: IStream readonly dispid 1;
    property OutputStream: IStream readonly dispid 2;
    property Property_[const par_name: WideString]: OleVariant dispid 3;
    procedure ConnectWSDL(const par_Port: IWSDLPort); dispid 4;
    procedure BeginMessageWSDL(const par_operation: IWSDLOperation); dispid 6;
    procedure EndMessage; dispid 7;
    procedure Reset; dispid 5;
    procedure Connect; dispid 8;
    procedure BeginMessage; dispid 9;
  end;

// *********************************************************************//
// Interface: ISoapConnectorFactory
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {0AF40C50-9257-11D5-87EA-00B0D0BE6479}
// *********************************************************************//
  ISoapConnectorFactory = interface(IDispatch)
    ['{0AF40C50-9257-11D5-87EA-00B0D0BE6479}']
    function  CreatePortConnector(const par_Port: IWSDLPort): ISoapConnector; safecall;
  end;

// *********************************************************************//
// DispIntf:  ISoapConnectorFactoryDisp
// Flags:     (4416) Dual OleAutomation Dispatchable
// GUID:      {0AF40C50-9257-11D5-87EA-00B0D0BE6479}
// *********************************************************************//
  ISoapConnectorFactoryDisp = dispinterface
    ['{0AF40C50-9257-11D5-87EA-00B0D0BE6479}']
    function  CreatePortConnector(const par_Port: IWSDLPort): ISoapConnector; dispid 1;
  end;

// *********************************************************************//
// Interface: ISoapError
// Flags:     (256) OleAutomation
// GUID:      {7F017F94-9257-11D5-87EA-00B0D0BE6479}
// *********************************************************************//
  ISoapError = interface(IUnknown)
    ['{7F017F94-9257-11D5-87EA-00B0D0BE6479}']
    function  Get_FaultCode(out par_FaultCode: WideString): HResult; stdcall;
    function  Get_FaultString(out par_FaultString: WideString): HResult; stdcall;
    function  Get_FaultActor(out par_Actor: WideString): HResult; stdcall;
    function  Get_Detail(out par_Detail: WideString): HResult; stdcall;
    function  Get_FaultCodeNamespace(out par_Namespace: WideString): HResult; stdcall;
  end;

// *********************************************************************//
// Interface: IErrorInfo
// Flags:     (0)
// GUID:      {1CF2B120-547D-101B-8E65-08002B2BD119}
// *********************************************************************//
  IErrorInfo = interface(IUnknown)
    ['{1CF2B120-547D-101B-8E65-08002B2BD119}']
    function  GetGUID(out pGUID: TGUID): HResult; stdcall;
    function  GetSource(out pBstrSource: WideString): HResult; stdcall;
    function  GetDescription(out pBstrDescription: WideString): HResult; stdcall;
    function  GetHelpFile(out pBstrHelpFile: WideString): HResult; stdcall;
    function  GetHelpContext(out pdwHelpContext: LongWord): HResult; stdcall;
  end;

// *********************************************************************//
// Interface: ISoapErrorInfo
// Flags:     (256) OleAutomation
// GUID:      {C0871607-8C99-4824-92CD-85CBD4C7273F}
// *********************************************************************//
  ISoapErrorInfo = interface(IErrorInfo)
    ['{C0871607-8C99-4824-92CD-85CBD4C7273F}']
    function  SetActor(const par_Actor: WideString): HResult; stdcall;
    function  SetFaultCode(const par_FaultCode: WideString): HResult; stdcall;
    function  AddErrorEntry(const par_Description: WideString; const par_Component: WideString; 
                            par_ErrorCode: HResult): HResult; stdcall;
    function  AddSoapError(const par_FaultString: WideString; const par_FaultActor: WideString; 
                           const par_Detail: WideString; const par_FaultCode: WideString; 
                           const par_Namespace: WideString): HResult; stdcall;
    function  AddErrorInfo(const par_Description: WideString; const par_source: WideString; 
                           const par_Helpfile: WideString; par_HelpContext: LongWord; 
                           par_hrFromErrorInfo: HResult): HResult; stdcall;
    function  LoadFault(const par_Document: IXMLDOMDocument): HResult; stdcall;
    function  GetHresult(out par_HR: HResult): HResult; stdcall;
    function  GetErrorEntry(par_EntryID: LongWord; out par_Description: WideString; 
                            out par_Component: WideString; out par_HR: HResult): HResult; stdcall;
    function  GetActor(out par_Actor: WideString): HResult; stdcall;
    function  GetErrorInfo(var par_Description: WideString; var par_source: WideString; 
                           var par_Helpfile: WideString; var par_HelpContext: LongWord; 
                           var par_hrFromErrorInfo: HResult): HResult; stdcall;
    function  GetSoapError(var par_FaultString: WideString; var par_FaultActor: WideString; 
                           var par_Detail: WideString; var par_FaultCode: WideString; 
                           var par_Namespace: WideString): HResult; stdcall;
  end;

// *********************************************************************//
// Interface: IGCTMObjectFactory
// Flags:     (256) OleAutomation
// GUID:      {3C87B8BE-F2B7-45C5-B34E-4A46A58A80B0}
// *********************************************************************//
  IGCTMObjectFactory = interface(IUnknown)
    ['{3C87B8BE-F2B7-45C5-B34E-4A46A58A80B0}']
    function  CreateObject(const par_WSMLNode: IXMLDOMNode; out par_Object: IDispatch): HResult; stdcall;
  end;

// *********************************************************************//
// The Class CoFileAttachment30 provides a Create and CreateRemote method to          
// create instances of the default interface IFileAttachment exposed by              
// the CoClass FileAttachment30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoFileAttachment30 = class
    class function Create: IFileAttachment;
    class function CreateRemote(const MachineName: string): IFileAttachment;
  end;

// *********************************************************************//
// The Class CoStringAttachment30 provides a Create and CreateRemote method to          
// create instances of the default interface IStringAttachment exposed by              
// the CoClass StringAttachment30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoStringAttachment30 = class
    class function Create: IStringAttachment;
    class function CreateRemote(const MachineName: string): IStringAttachment;
  end;

// *********************************************************************//
// The Class CoByteArrayAttachment30 provides a Create and CreateRemote method to          
// create instances of the default interface IByteArrayAttachment exposed by              
// the CoClass ByteArrayAttachment30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoByteArrayAttachment30 = class
    class function Create: IByteArrayAttachment;
    class function CreateRemote(const MachineName: string): IByteArrayAttachment;
  end;

// *********************************************************************//
// The Class CoStreamAttachment30 provides a Create and CreateRemote method to          
// create instances of the default interface IStreamAttachment exposed by              
// the CoClass StreamAttachment30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoStreamAttachment30 = class
    class function Create: IStreamAttachment;
    class function CreateRemote(const MachineName: string): IStreamAttachment;
  end;

// *********************************************************************//
// The Class CoSentAttachments30 provides a Create and CreateRemote method to          
// create instances of the default interface ISentAttachments exposed by              
// the CoClass SentAttachments30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoSentAttachments30 = class
    class function Create: ISentAttachments;
    class function CreateRemote(const MachineName: string): ISentAttachments;
  end;

// *********************************************************************//
// The Class CoReceivedAttachments30 provides a Create and CreateRemote method to          
// create instances of the default interface IReceivedAttachments exposed by              
// the CoClass ReceivedAttachments30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoReceivedAttachments30 = class
    class function Create: IReceivedAttachments;
    class function CreateRemote(const MachineName: string): IReceivedAttachments;
  end;

// *********************************************************************//
// The Class CoDataEncoderFactory30 provides a Create and CreateRemote method to          
// create instances of the default interface IDataEncoderFactory exposed by              
// the CoClass DataEncoderFactory30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoDataEncoderFactory30 = class
    class function Create: IDataEncoderFactory;
    class function CreateRemote(const MachineName: string): IDataEncoderFactory;
  end;

// *********************************************************************//
// The Class CoDimeComposer30 provides a Create and CreateRemote method to          
// create instances of the default interface IDimeComposer exposed by              
// the CoClass DimeComposer30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoDimeComposer30 = class
    class function Create: IDimeComposer;
    class function CreateRemote(const MachineName: string): IDimeComposer;
  end;

// *********************************************************************//
// The Class CoDimeParser30 provides a Create and CreateRemote method to          
// create instances of the default interface IDimeParser exposed by              
// the CoClass DimeParser30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoDimeParser30 = class
    class function Create: IDimeParser;
    class function CreateRemote(const MachineName: string): IDimeParser;
  end;

// *********************************************************************//
// The Class CoSimpleComposer30 provides a Create and CreateRemote method to          
// create instances of the default interface ISimpleComposer exposed by              
// the CoClass SimpleComposer30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoSimpleComposer30 = class
    class function Create: ISimpleComposer;
    class function CreateRemote(const MachineName: string): ISimpleComposer;
  end;

// *********************************************************************//
// The Class CoSimpleParser30 provides a Create and CreateRemote method to          
// create instances of the default interface ISimpleParser exposed by              
// the CoClass SimpleParser30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoSimpleParser30 = class
    class function Create: ISimpleParser;
    class function CreateRemote(const MachineName: string): ISimpleParser;
  end;

// *********************************************************************//
// The Class CoSoapReader30 provides a Create and CreateRemote method to          
// create instances of the default interface ISoapReader exposed by              
// the CoClass SoapReader30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoSoapReader30 = class
    class function Create: ISoapReader;
    class function CreateRemote(const MachineName: string): ISoapReader;
  end;

// *********************************************************************//
// The Class CoSoapSerializer30 provides a Create and CreateRemote method to          
// create instances of the default interface ISoapSerializer exposed by              
// the CoClass SoapSerializer30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoSoapSerializer30 = class
    class function Create: ISoapSerializer;
    class function CreateRemote(const MachineName: string): ISoapSerializer;
  end;

// *********************************************************************//
// The Class CoSoapServer30 provides a Create and CreateRemote method to          
// create instances of the default interface ISoapServer exposed by              
// the CoClass SoapServer30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoSoapServer30 = class
    class function Create: ISoapServer;
    class function CreateRemote(const MachineName: string): ISoapServer;
  end;

// *********************************************************************//
// The Class CoSoapClient30 provides a Create and CreateRemote method to          
// create instances of the default interface ISoapClient exposed by              
// the CoClass SoapClient30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoSoapClient30 = class
    class function Create: ISoapClient;
    class function CreateRemote(const MachineName: string): ISoapClient;
  end;

// *********************************************************************//
// The Class CoWSDLReader30 provides a Create and CreateRemote method to          
// create instances of the default interface IWSDLReader exposed by              
// the CoClass WSDLReader30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoWSDLReader30 = class
    class function Create: IWSDLReader;
    class function CreateRemote(const MachineName: string): IWSDLReader;
  end;

// *********************************************************************//
// The Class CoSoapTypeMapperFactory30 provides a Create and CreateRemote method to          
// create instances of the default interface ISoapTypeMapperFactory exposed by              
// the CoClass SoapTypeMapperFactory30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoSoapTypeMapperFactory30 = class
    class function Create: ISoapTypeMapperFactory;
    class function CreateRemote(const MachineName: string): ISoapTypeMapperFactory;
  end;

// *********************************************************************//
// The Class CoGenericCustomTypeMapper30 provides a Create and CreateRemote method to          
// create instances of the default interface IDispatch exposed by              
// the CoClass GenericCustomTypeMapper30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoGenericCustomTypeMapper30 = class
    class function Create: IDispatch;
    class function CreateRemote(const MachineName: string): IDispatch;
  end;

// *********************************************************************//
// The Class CoUDTMapper30 provides a Create and CreateRemote method to          
// create instances of the default interface IDispatch exposed by              
// the CoClass UDTMapper30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoUDTMapper30 = class
    class function Create: IDispatch;
    class function CreateRemote(const MachineName: string): IDispatch;
  end;

// *********************************************************************//
// The Class CoSoapConnector30 provides a Create and CreateRemote method to          
// create instances of the default interface ISoapConnector exposed by              
// the CoClass SoapConnector30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoSoapConnector30 = class
    class function Create: ISoapConnector;
    class function CreateRemote(const MachineName: string): ISoapConnector;
  end;

// *********************************************************************//
// The Class CoSoapConnectorFactory30 provides a Create and CreateRemote method to          
// create instances of the default interface ISoapConnectorFactory exposed by              
// the CoClass SoapConnectorFactory30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoSoapConnectorFactory30 = class
    class function Create: ISoapConnectorFactory;
    class function CreateRemote(const MachineName: string): ISoapConnectorFactory;
  end;

// *********************************************************************//
// The Class CoHttpConnector30 provides a Create and CreateRemote method to          
// create instances of the default interface ISoapConnector exposed by              
// the CoClass HttpConnector30. The functions are intended to be used by             
// clients wishing to automate the CoClass objects exposed by the         
// server of this typelibrary.                                            
// *********************************************************************//
  CoHttpConnector30 = class
    class function Create: ISoapConnector;
    class function CreateRemote(const MachineName: string): ISoapConnector;
  end;

implementation

uses ComObj;

class function CoFileAttachment30.Create: IFileAttachment;
begin
  Result := CreateComObject(CLASS_FileAttachment30) as IFileAttachment;
end;

class function CoFileAttachment30.CreateRemote(const MachineName: string): IFileAttachment;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_FileAttachment30) as IFileAttachment;
end;

class function CoStringAttachment30.Create: IStringAttachment;
begin
  Result := CreateComObject(CLASS_StringAttachment30) as IStringAttachment;
end;

class function CoStringAttachment30.CreateRemote(const MachineName: string): IStringAttachment;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_StringAttachment30) as IStringAttachment;
end;

class function CoByteArrayAttachment30.Create: IByteArrayAttachment;
begin
  Result := CreateComObject(CLASS_ByteArrayAttachment30) as IByteArrayAttachment;
end;

class function CoByteArrayAttachment30.CreateRemote(const MachineName: string): IByteArrayAttachment;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_ByteArrayAttachment30) as IByteArrayAttachment;
end;

class function CoStreamAttachment30.Create: IStreamAttachment;
begin
  Result := CreateComObject(CLASS_StreamAttachment30) as IStreamAttachment;
end;

class function CoStreamAttachment30.CreateRemote(const MachineName: string): IStreamAttachment;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_StreamAttachment30) as IStreamAttachment;
end;

class function CoSentAttachments30.Create: ISentAttachments;
begin
  Result := CreateComObject(CLASS_SentAttachments30) as ISentAttachments;
end;

class function CoSentAttachments30.CreateRemote(const MachineName: string): ISentAttachments;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_SentAttachments30) as ISentAttachments;
end;

class function CoReceivedAttachments30.Create: IReceivedAttachments;
begin
  Result := CreateComObject(CLASS_ReceivedAttachments30) as IReceivedAttachments;
end;

class function CoReceivedAttachments30.CreateRemote(const MachineName: string): IReceivedAttachments;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_ReceivedAttachments30) as IReceivedAttachments;
end;

class function CoDataEncoderFactory30.Create: IDataEncoderFactory;
begin
  Result := CreateComObject(CLASS_DataEncoderFactory30) as IDataEncoderFactory;
end;

class function CoDataEncoderFactory30.CreateRemote(const MachineName: string): IDataEncoderFactory;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_DataEncoderFactory30) as IDataEncoderFactory;
end;

class function CoDimeComposer30.Create: IDimeComposer;
begin
  Result := CreateComObject(CLASS_DimeComposer30) as IDimeComposer;
end;

class function CoDimeComposer30.CreateRemote(const MachineName: string): IDimeComposer;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_DimeComposer30) as IDimeComposer;
end;

class function CoDimeParser30.Create: IDimeParser;
begin
  Result := CreateComObject(CLASS_DimeParser30) as IDimeParser;
end;

class function CoDimeParser30.CreateRemote(const MachineName: string): IDimeParser;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_DimeParser30) as IDimeParser;
end;

class function CoSimpleComposer30.Create: ISimpleComposer;
begin
  Result := CreateComObject(CLASS_SimpleComposer30) as ISimpleComposer;
end;

class function CoSimpleComposer30.CreateRemote(const MachineName: string): ISimpleComposer;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_SimpleComposer30) as ISimpleComposer;
end;

class function CoSimpleParser30.Create: ISimpleParser;
begin
  Result := CreateComObject(CLASS_SimpleParser30) as ISimpleParser;
end;

class function CoSimpleParser30.CreateRemote(const MachineName: string): ISimpleParser;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_SimpleParser30) as ISimpleParser;
end;

class function CoSoapReader30.Create: ISoapReader;
begin
  Result := CreateComObject(CLASS_SoapReader30) as ISoapReader;
end;

class function CoSoapReader30.CreateRemote(const MachineName: string): ISoapReader;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_SoapReader30) as ISoapReader;
end;

class function CoSoapSerializer30.Create: ISoapSerializer;
begin
  Result := CreateComObject(CLASS_SoapSerializer30) as ISoapSerializer;
end;

class function CoSoapSerializer30.CreateRemote(const MachineName: string): ISoapSerializer;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_SoapSerializer30) as ISoapSerializer;
end;

class function CoSoapServer30.Create: ISoapServer;
begin
  Result := CreateComObject(CLASS_SoapServer30) as ISoapServer;
end;

class function CoSoapServer30.CreateRemote(const MachineName: string): ISoapServer;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_SoapServer30) as ISoapServer;
end;

class function CoSoapClient30.Create: ISoapClient;
begin
  Result := CreateComObject(CLASS_SoapClient30) as ISoapClient;
end;

class function CoSoapClient30.CreateRemote(const MachineName: string): ISoapClient;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_SoapClient30) as ISoapClient;
end;

class function CoWSDLReader30.Create: IWSDLReader;
begin
  Result := CreateComObject(CLASS_WSDLReader30) as IWSDLReader;
end;

class function CoWSDLReader30.CreateRemote(const MachineName: string): IWSDLReader;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_WSDLReader30) as IWSDLReader;
end;

class function CoSoapTypeMapperFactory30.Create: ISoapTypeMapperFactory;
begin
  Result := CreateComObject(CLASS_SoapTypeMapperFactory30) as ISoapTypeMapperFactory;
end;

class function CoSoapTypeMapperFactory30.CreateRemote(const MachineName: string): ISoapTypeMapperFactory;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_SoapTypeMapperFactory30) as ISoapTypeMapperFactory;
end;

class function CoGenericCustomTypeMapper30.Create: IDispatch;
begin
  Result := CreateComObject(CLASS_GenericCustomTypeMapper30) as IDispatch;
end;

class function CoGenericCustomTypeMapper30.CreateRemote(const MachineName: string): IDispatch;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_GenericCustomTypeMapper30) as IDispatch;
end;

class function CoUDTMapper30.Create: IDispatch;
begin
  Result := CreateComObject(CLASS_UDTMapper30) as IDispatch;
end;

class function CoUDTMapper30.CreateRemote(const MachineName: string): IDispatch;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_UDTMapper30) as IDispatch;
end;

class function CoSoapConnector30.Create: ISoapConnector;
begin
  Result := CreateComObject(CLASS_SoapConnector30) as ISoapConnector;
end;

class function CoSoapConnector30.CreateRemote(const MachineName: string): ISoapConnector;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_SoapConnector30) as ISoapConnector;
end;

class function CoSoapConnectorFactory30.Create: ISoapConnectorFactory;
begin
  Result := CreateComObject(CLASS_SoapConnectorFactory30) as ISoapConnectorFactory;
end;

class function CoSoapConnectorFactory30.CreateRemote(const MachineName: string): ISoapConnectorFactory;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_SoapConnectorFactory30) as ISoapConnectorFactory;
end;

class function CoHttpConnector30.Create: ISoapConnector;
begin
  Result := CreateComObject(CLASS_HttpConnector30) as ISoapConnector;
end;

class function CoHttpConnector30.CreateRemote(const MachineName: string): ISoapConnector;
begin
  Result := CreateRemoteComObject(MachineName, CLASS_HttpConnector30) as ISoapConnector;
end;

end.
