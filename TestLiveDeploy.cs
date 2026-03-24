using System;
using System.Windows.Forms;
using GTA;

namespace LiveModding
{
    public class TestLiveDeployScript : Script
    {
        public TestLiveDeployScript()
        {
            Game.DisplayText("Live reload test v2 loaded from desktop clone.", 4000);
            BindKey(Keys.F9, new KeyPressDelegate(ShowPing));
        }

        private void ShowPing()
        {
            Game.DisplayText("F9 ping from live reload test v2.", 2500);
        }
    }
}
