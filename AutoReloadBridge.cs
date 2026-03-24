using System;
using System.IO;
using GTA;

namespace LiveModding
{
    public class AutoReloadBridgeScript : Script
    {
        private static readonly string TriggerPath =
            @"C:\Program Files (x86)\Steam\steamapps\common\Grand Theft Auto IV\Modding\LiveModding\.reload_request";
        private static readonly string ConsumedPath =
            @"C:\Program Files (x86)\Steam\steamapps\common\Grand Theft Auto IV\Modding\LiveModding\.reload_consumed";

        private int nextCheckTime;
        private bool reloadIssued;

        public AutoReloadBridgeScript()
        {
            Interval = 250;
            Tick += new EventHandler(OnTick);
        }

        private void OnTick(object sender, EventArgs e)
        {
            if (Game.GameTime < nextCheckTime)
            {
                return;
            }

            nextCheckTime = Game.GameTime + 250;

            if (!File.Exists(TriggerPath))
            {
                reloadIssued = false;
                return;
            }

            if (reloadIssued)
            {
                return;
            }

            string requestedCommitSha;
            try
            {
                requestedCommitSha = File.ReadAllText(TriggerPath).Trim();
                File.Delete(TriggerPath);
            }
            catch
            {
                return;
            }

            if (string.IsNullOrEmpty(requestedCommitSha))
            {
                requestedCommitSha = "unknown";
            }

            try
            {
                File.WriteAllText(ConsumedPath, requestedCommitSha + Environment.NewLine);
            }
            catch
            {
            }

            reloadIssued = true;
            Game.DisplayText("LiveModding reload requested: " + requestedCommitSha, 2000);
            Game.Console.SendCommand("ReloadScripts");
        }
    }
}
