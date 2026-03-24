using System;
using System.Windows.Forms;
using GTA;

namespace LiveModding
{
    public class TestLiveDeployScript : Script
    {
        public TestLiveDeployScript()
        {
            Game.DisplayText("Live test script loaded from desktop clone.", 3000);
            BindKey(Keys.F9, new KeyPressDelegate(ShowPing));
        }

        private void ShowPing()
        {
            Game.DisplayText("F9 ping from desktop test clone.", 2000);
        }
    }
}
