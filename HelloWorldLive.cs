using System.Windows.Forms;
using GTA;

namespace LiveModding
{
    public class HelloWorldLiveScript : Script
    {
        public HelloWorldLiveScript()
        {
            BindKey(Keys.F5, new KeyPressDelegate(ShowHelloWorld));
        }

        private void ShowHelloWorld()
        {
            Game.DisplayText("Hello from LiveModding!", 2000);
        }
    }
}
