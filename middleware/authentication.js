const {validateToken}=require("../services/authentication");
function checkForAuthenticationCookie(cookieName){
    return (req,res,next)=>{
        //console.log("cookies",req.cookies);
        const tokenCookieValue=req.cookies[cookieName];
        if(!tokenCookieValue){
          return  next();
        }
    
    try {
        const userPayLoad=validateToken(tokenCookieValue);
        req.user=userPayLoad;
       // console.log("User payload",req.user);
    } catch (error) {}
   return next();
};
}
module.exports={
    checkForAuthenticationCookie,
}