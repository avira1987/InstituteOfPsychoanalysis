<%@ Page Title="Home Page" Language="C#" AutoEventWireup="true"
    CodeBehind="Default.aspx.cs" Inherits="PGA_ASPNET._Default" %>
    <body>
<form action="https://acquirer.samanepay.com/payment.aspx" method="post">
  <input type="hidden" id="Amount" name="Amount" value="1000"/>
  <input type="hidden" id="MID" name="MID" value="2031"/>
  <input type="hidden" id="ResNum" name="ResNum" value="1021"/>
  <input type="hidden" id="Wage" name="Wage" value="0"/>
  <input type="hidden" id="RedirectURL" name="RedirectURL" value="http://localhost:7725/Default.aspx"/>
 
 <div style="clear: both;">
            <button type="submit" name="Save" class='t-button t-state-default'>خرید اینترنتی</button>
    </div>
    </form>
</body>